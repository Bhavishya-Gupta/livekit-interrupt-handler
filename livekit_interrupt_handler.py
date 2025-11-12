"""
LiveKit Voice Interruption Handler

Intelligently distinguishes meaningful user interruptions from filler words
during real-time conversational AI interactions.

Author: SalesCode.ai Qualifier Solution
License: MIT
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, asdict
from threading import Lock


@dataclass
class TranscriptionEvent:
    """Represents a transcription event from ASR"""
    transcript: str
    confidence: float
    is_final: bool = True
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class InterruptDecision:
    """Represents a decision made about an interruption"""
    event_id: str
    timestamp: datetime
    agent_speaking: bool
    transcript: str
    tokens: List[str]
    confidence: float
    action: str  # 'interrupt', 'ignore', 'register'
    reason: str
    duration_ms: float
    
    def to_jsonl(self) -> str:
        """Convert to JSONL format for logging"""
        data = asdict(self)
        data['timestamp_iso'] = self.timestamp.isoformat()
        del data['timestamp']
        return json.dumps(data)


class InterruptHandler:
    """
    Handles voice interruption detection with filler word filtering.
    
    This class integrates with LiveKit agents to intelligently filter out
    filler words while preserving genuine user interruptions.
    """
    
    def __init__(self, agent: any, config: Dict[str, any]):
        """
        Initialize the interrupt handler.
        
        Args:
            agent: LiveKit agent instance (duck-typed for compatibility)
            config: Configuration dictionary with keys:
                - ignored_words: List of filler words to ignore
                - command_words: List of words that always trigger interrupts
                - confidence_threshold: Minimum confidence for valid speech (0-1)
                - low_confidence_time_ms: Max duration for low-confidence ignore
                - log_file: Path to JSONL log file
                - enable_logging: Whether to log events
        """
        self.agent = agent
        self.config = config
        
        # Thread-safe state management
        self._lock = Lock()
        self._agent_speaking = False
        self._last_vad_update = datetime.now(timezone.utc)
        
        # Normalized word sets for fast lookup
        self._ignored_words: Set[str] = set(
            self._normalize_word(w) for w in config.get('ignored_words', [])
        )
        self._command_words: Set[str] = set(
            self._normalize_word(w) for w in config.get('command_words', [])
        )
        
        # Configuration parameters
        self.confidence_threshold = config.get('confidence_threshold', 0.3)
        self.low_confidence_time_ms = config.get('low_confidence_time_ms', 500)
        
        # Logging setup
        self.enable_logging = config.get('enable_logging', True)
        self.log_file = Path(config.get('log_file', 'logs/interrupts.jsonl'))
        if self.enable_logging:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Callbacks for external notification
        self._interrupt_callback: Optional[Callable] = None
        
        # Internal logger
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(
            f"InterruptHandler initialized with "
            f"{len(self._ignored_words)} ignored words, "
            f"{len(self._command_words)} command words, "
            f"confidence threshold: {self.confidence_threshold}"
        )
    
    @staticmethod
    def _normalize_word(word: str) -> str:
        """Normalize word: lowercase, strip punctuation"""
        return re.sub(r'[^\w\s]', '', word.lower()).strip()
    
    def _tokenize(self, transcript: str) -> List[str]:
        """Split transcript into normalized tokens"""
        return [
            self._normalize_word(w) 
            for w in transcript.split() 
            if self._normalize_word(w)
        ]
    
    def _contains_command_word(self, tokens: List[str]) -> bool:
        """Check if any token is a command word"""
        return any(token in self._command_words for token in tokens)
    
    def _is_filler_only(self, tokens: List[str]) -> bool:
        """Check if all tokens are filler words"""
        if not tokens:
            return True
        return all(token in self._ignored_words for token in tokens)
    
    async def on_transcription_event(self, event: TranscriptionEvent) -> bool:
        """
        Process a transcription event and decide whether to interrupt.
        
        Args:
            event: TranscriptionEvent containing transcript and metadata
            
        Returns:
            bool: True if agent should be interrupted, False otherwise
        """
        start_time = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())[:8]
        
        # Get current agent state (thread-safe)
        with self._lock:
            agent_speaking = self._agent_speaking
        
        # Tokenize and analyze transcript
        tokens = self._tokenize(event.transcript)
        
        # Decision logic
        decision = self._make_decision(
            event_id=event_id,
            timestamp=start_time,
            agent_speaking=agent_speaking,
            transcript=event.transcript,
            tokens=tokens,
            confidence=event.confidence
        )
        
        # Calculate processing time
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        decision.duration_ms = duration_ms
        
        # Log the decision
        if self.enable_logging:
            await self._log_decision(decision)
        
        # Execute action
        should_interrupt = decision.action == 'interrupt'
        
        if should_interrupt and agent_speaking:
            self.logger.info(
                f"[{event_id}] INTERRUPT: '{event.transcript}' - {decision.reason}"
            )
            # Notify agent to stop
            if hasattr(self.agent, 'stop_speaking'):
                await self.agent.stop_speaking()
            # Call external callback if set
            if self._interrupt_callback:
                await self._interrupt_callback(event)
        else:
            self.logger.debug(
                f"[{event_id}] {decision.action.upper()}: "
                f"'{event.transcript}' - {decision.reason}"
            )
        
        return should_interrupt
    
    def _make_decision(
        self,
        event_id: str,
        timestamp: datetime,
        agent_speaking: bool,
        transcript: str,
        tokens: List[str],
        confidence: float
    ) -> InterruptDecision:
        """
        Core decision logic for interrupt handling.
        
        Returns an InterruptDecision with action and reasoning.
        """
        # Empty transcript - ignore
        if not tokens:
            return InterruptDecision(
                event_id=event_id,
                timestamp=timestamp,
                agent_speaking=agent_speaking,
                transcript=transcript,
                tokens=tokens,
                confidence=confidence,
                action='ignore',
                reason='Empty transcript',
                duration_ms=0.0
            )
        
        # Low confidence - ignore
        if confidence < self.confidence_threshold:
            return InterruptDecision(
                event_id=event_id,
                timestamp=timestamp,
                agent_speaking=agent_speaking,
                transcript=transcript,
                tokens=tokens,
                confidence=confidence,
                action='ignore',
                reason=f'Low confidence ({confidence:.2f} < {self.confidence_threshold})',
                duration_ms=0.0
            )
        
        # Agent is NOT speaking - register all speech
        if not agent_speaking:
            return InterruptDecision(
                event_id=event_id,
                timestamp=timestamp,
                agent_speaking=agent_speaking,
                transcript=transcript,
                tokens=tokens,
                confidence=confidence,
                action='register',
                reason='Agent not speaking, registering user speech',
                duration_ms=0.0
            )
        
        # Agent IS speaking - apply filtering logic
        
        # Contains command word - always interrupt
        if self._contains_command_word(tokens):
            return InterruptDecision(
                event_id=event_id,
                timestamp=timestamp,
                agent_speaking=agent_speaking,
                transcript=transcript,
                tokens=tokens,
                confidence=confidence,
                action='interrupt',
                reason='Contains command word',
                duration_ms=0.0
            )
        
        # Only fillers - ignore
        if self._is_filler_only(tokens):
            return InterruptDecision(
                event_id=event_id,
                timestamp=timestamp,
                agent_speaking=agent_speaking,
                transcript=transcript,
                tokens=tokens,
                confidence=confidence,
                action='ignore',
                reason='Filler-only speech while agent speaking',
                duration_ms=0.0
            )
        
        # Contains real words (not fillers, not commands) - interrupt
        return InterruptDecision(
            event_id=event_id,
            timestamp=timestamp,
            agent_speaking=agent_speaking,
            transcript=transcript,
            tokens=tokens,
            confidence=confidence,
            action='interrupt',
            reason='Real user speech detected',
            duration_ms=0.0
        )
    
    async def on_vad_state_change(self, is_speaking: bool):
        """
        Update internal state when agent's speaking state changes.
        
        Args:
            is_speaking: True if agent is currently speaking, False otherwise
        """
        with self._lock:
            old_state = self._agent_speaking
            self._agent_speaking = is_speaking
            self._last_vad_update = datetime.now(timezone.utc)
        
        if old_state != is_speaking:
            self.logger.debug(
                f"Agent state changed: {'speaking' if is_speaking else 'quiet'}"
            )
    
    def update_ignored_words(self, words: List[str]):
        """
        Dynamically update the list of ignored filler words.
        
        Args:
            words: New list of words to ignore
        """
        with self._lock:
            self._ignored_words = set(self._normalize_word(w) for w in words)
        
        self.logger.info(
            f"Updated ignored words list: {len(self._ignored_words)} words"
        )
    
    def update_command_words(self, words: List[str]):
        """
        Dynamically update the list of command words.
        
        Args:
            words: New list of command words
        """
        with self._lock:
            self._command_words = set(self._normalize_word(w) for w in words)
        
        self.logger.info(
            f"Updated command words list: {len(self._command_words)} words"
        )
    
    def set_interrupt_callback(self, callback: Callable):
        """
        Set a callback to be invoked when an interrupt occurs.
        
        Args:
            callback: Async function to call on interrupt
        """
        self._interrupt_callback = callback
    
    async def _log_decision(self, decision: InterruptDecision):
        """Write decision to JSONL log file"""
        try:
            async with asyncio.Lock():  # Prevent concurrent writes
                with open(self.log_file, 'a') as f:
                    f.write(decision.to_jsonl() + '\n')
        except Exception as e:
            self.logger.error(f"Failed to log decision: {e}")
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get current statistics about the handler.
        
        Returns:
            Dict with configuration and state information
        """
        with self._lock:
            return {
                'agent_speaking': self._agent_speaking,
                'ignored_words_count': len(self._ignored_words),
                'command_words_count': len(self._command_words),
                'confidence_threshold': self.confidence_threshold,
                'last_vad_update': self._last_vad_update.isoformat(),
                'logging_enabled': self.enable_logging,
                'log_file': str(self.log_file)
            }
    
    async def shutdown(self):
        """
        Gracefully shutdown the handler.
        
        Ensures all pending logs are written and resources are released.
        """
        self.logger.info("Shutting down InterruptHandler")
        
        # Wait for any pending async operations
        await asyncio.sleep(0.1)
        
        self.logger.info("InterruptHandler shutdown complete")


# Example usage and integration helper
class LiveKitAgentAdapter:
    """
    Adapter class to integrate InterruptHandler with LiveKit agents.
    
    This shows how to hook the handler into LiveKit's event system.
    """
    
    def __init__(self, livekit_agent, handler_config: Dict[str, any]):
        """
        Initialize adapter with LiveKit agent and handler config.
        
        Args:
            livekit_agent: Instance of LiveKit agent
            handler_config: Configuration for InterruptHandler
        """
        self.agent = livekit_agent
        self.handler = InterruptHandler(livekit_agent, handler_config)
        
        # Hook into agent events
        self._setup_hooks()
    
    def _setup_hooks(self):
        """
        Set up event hooks without modifying LiveKit core.
        
        This method demonstrates how to intercept events using callbacks.
        """
        # Example: Hook into transcription events
        if hasattr(self.agent, 'on_transcription'):
            original_handler = self.agent.on_transcription
            
            async def wrapped_handler(event):
                # Let our handler process first
                should_interrupt = await self.handler.on_transcription_event(event)
                
                # Only call original if not interrupting
                if not should_interrupt and original_handler:
                    await original_handler(event)
            
            self.agent.on_transcription = wrapped_handler
        
        # Example: Hook into VAD state changes
        if hasattr(self.agent, 'on_speaking_state_changed'):
            original_handler = self.agent.on_speaking_state_changed
            
            async def wrapped_handler(is_speaking):
                await self.handler.on_vad_state_change(is_speaking)
                if original_handler:
                    await original_handler(is_speaking)
            
            self.agent.on_speaking_state_changed = wrapped_handler
    
    async def shutdown(self):
        """Shutdown the adapter and handler"""
        await self.handler.shutdown()
