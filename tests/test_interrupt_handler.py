"""
Comprehensive test suite for LiveKit Interrupt Handler.

Tests all scenarios from the assignment specification.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from livekit_interrupt_handler import (
    InterruptHandler,
    TranscriptionEvent,
    InterruptDecision
)


class MockAgent:
    """Mock LiveKit agent for testing"""
    
    def __init__(self):
        self.stop_speaking = AsyncMock()
        self.speaking_stopped_count = 0
    
    async def stop_speaking(self):
        """Mock stop speaking method"""
        self.speaking_stopped_count += 1


@pytest.fixture
def temp_log_file():
    """Create temporary log file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        log_path = Path(f.name)
    yield log_path
    if log_path.exists():
        log_path.unlink()


@pytest.fixture
def mock_agent():
    """Create mock agent"""
    return MockAgent()


@pytest.fixture
def basic_config(temp_log_file):
    """Basic test configuration"""
    return {
        'ignored_words': ['uh', 'umm', 'hmm', 'haan'],
        'command_words': ['wait', 'stop', 'no', 'hold'],
        'confidence_threshold': 0.3,
        'low_confidence_time_ms': 500,
        'log_file': str(temp_log_file),
        'enable_logging': True
    }


@pytest.fixture
def handler(mock_agent, basic_config):
    """Create handler instance"""
    return InterruptHandler(mock_agent, basic_config)


# ============================================================================
# Test 1: Filler-Only Speech While Agent Speaking
# ============================================================================

@pytest.mark.asyncio
async def test_filler_only_while_speaking_ignores(handler):
    """
    Scenario: User says only fillers while agent is speaking
    Expected: Agent ignores and continues speaking
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    # Test various filler-only inputs
    filler_inputs = [
        'uh',
        'umm',
        'hmm',
        'uh umm',
        'hmm uh',
        'haan'
    ]
    
    for filler in filler_inputs:
        event = TranscriptionEvent(
            transcript=filler,
            confidence=0.8,
            is_final=True
        )
        
        should_interrupt = await handler.on_transcription_event(event)
        
        assert should_interrupt is False, f"Should not interrupt for '{filler}'"
        assert handler.agent.speaking_stopped_count == 0, \
            "Agent should not have been stopped"


# ============================================================================
# Test 2: Real Interruption While Agent Speaking
# ============================================================================

@pytest.mark.asyncio
async def test_real_interruption_while_speaking_stops(handler):
    """
    Scenario: User says real words while agent is speaking
    Expected: Agent stops immediately
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    # Test various real interruptions
    real_inputs = [
        'wait one second',
        'no not that one',
        'stop please',
        'actually I meant',
        'hold on'
    ]
    
    for idx, real_speech in enumerate(real_inputs, 1):
        event = TranscriptionEvent(
            transcript=real_speech,
            confidence=0.8,
            is_final=True
        )
        
        should_interrupt = await handler.on_transcription_event(event)
        
        assert should_interrupt is True, \
            f"Should interrupt for '{real_speech}'"
        assert handler.agent.speaking_stopped_count == idx, \
            f"Agent should have been stopped {idx} times"


# ============================================================================
# Test 3: Filler While Agent Quiet
# ============================================================================

@pytest.mark.asyncio
async def test_filler_while_quiet_registers(handler):
    """
    Scenario: User says filler while agent is quiet
    Expected: Speech is registered as valid user input
    """
    # Set agent to quiet state
    await handler.on_vad_state_change(is_speaking=False)
    
    event = TranscriptionEvent(
        transcript='umm',
        confidence=0.7,
        is_final=True
    )
    
    should_interrupt = await handler.on_transcription_event(event)
    
    # When agent is quiet, we don't "interrupt" (nothing to interrupt)
    # but we also don't ignore - action should be "register"
    assert should_interrupt is False  # No interrupt needed when quiet
    assert handler.agent.speaking_stopped_count == 0


# ============================================================================
# Test 4: Mixed Filler and Command
# ============================================================================

@pytest.mark.asyncio
async def test_mixed_filler_and_command_stops(handler):
    """
    Scenario: User says filler + command word while agent speaking
    Expected: Agent stops (contains valid command)
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    mixed_inputs = [
        'umm okay stop',
        'uh wait',
        'hmm no',
        'uh hold on'
    ]
    
    for idx, mixed_speech in enumerate(mixed_inputs, 1):
        event = TranscriptionEvent(
            transcript=mixed_speech,
            confidence=0.8,
            is_final=True
        )
        
        should_interrupt = await handler.on_transcription_event(event)
        
        assert should_interrupt is True, \
            f"Should interrupt for '{mixed_speech}' (contains command)"


# ============================================================================
# Test 5: Low Confidence Speech
# ============================================================================

@pytest.mark.asyncio
async def test_low_confidence_ignored(handler):
    """
    Scenario: Low confidence transcription (background noise)
    Expected: Ignored regardless of content
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    # Test with various confidence levels below threshold
    low_confidence_inputs = [
        ('hmm yeah', 0.1),
        ('stop please', 0.2),
        ('wait', 0.25)
    ]
    
    for transcript, confidence in low_confidence_inputs:
        event = TranscriptionEvent(
            transcript=transcript,
            confidence=confidence,
            is_final=True
        )
        
        should_interrupt = await handler.on_transcription_event(event)
        
        assert should_interrupt is False, \
            f"Should ignore low confidence ({confidence}) '{transcript}'"


# ============================================================================
# Test 6: Empty or Whitespace Transcripts
# ============================================================================

@pytest.mark.asyncio
async def test_empty_transcript_ignored(handler):
    """
    Scenario: Empty or whitespace-only transcript
    Expected: Ignored
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    empty_inputs = ['', '   ', '\n', '\t']
    
    for empty in empty_inputs:
        event = TranscriptionEvent(
            transcript=empty,
            confidence=0.8,
            is_final=True
        )
        
        should_interrupt = await handler.on_transcription_event(event)
        
        assert should_interrupt is False, \
            f"Should ignore empty transcript '{repr(empty)}'"


# ============================================================================
# Test 7: Punctuation and Case Insensitivity
# ============================================================================

@pytest.mark.asyncio
async def test_punctuation_and_case_handling(handler):
    """
    Scenario: Test that punctuation is stripped and case is normalized
    Expected: Proper recognition regardless of case/punctuation
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    # Test filler with different case and punctuation
    filler_variants = [
        'UH',
        'Umm.',
        'HMM!',
        'uh...',
        'UMM???'
    ]
    
    for variant in filler_variants:
        event = TranscriptionEvent(
            transcript=variant,
            confidence=0.8,
            is_final=True
        )
        
        should_interrupt = await handler.on_transcription_event(event)
        
        assert should_interrupt is False, \
            f"Should recognize '{variant}' as filler"
    
    # Test command with different case and punctuation
    command_variants = [
        'WAIT',
        'Stop!',
        'No.',
        'HOLD ON!'
    ]
    
    for idx, variant in enumerate(command_variants, 1):
        event = TranscriptionEvent(
            transcript=variant,
            confidence=0.8,
            is_final=True
        )
        
        should_interrupt = await handler.on_transcription_event(event)
        
        assert should_interrupt is True, \
            f"Should recognize '{variant}' as command"


# ============================================================================
# Test 8: Dynamic Word List Updates
# ============================================================================

@pytest.mark.asyncio
async def test_dynamic_word_list_update(handler):
    """
    Scenario: Update ignored words list at runtime
    Expected: New words are immediately recognized
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    # Initially, 'yeah' is not in ignored list
    event = TranscriptionEvent(
        transcript='yeah',
        confidence=0.8,
        is_final=True
    )
    
    should_interrupt = await handler.on_transcription_event(event)
    assert should_interrupt is True, "'yeah' should initially cause interrupt"
    
    # Update ignored words to include 'yeah'
    new_ignored = ['uh', 'umm', 'hmm', 'haan', 'yeah']
    handler.update_ignored_words(new_ignored)
    
    # Now 'yeah' should be ignored
    event2 = TranscriptionEvent(
        transcript='yeah',
        confidence=0.8,
        is_final=True
    )
    
    should_interrupt2 = await handler.on_transcription_event(event2)
    assert should_interrupt2 is False, "'yeah' should now be ignored"


# ============================================================================
# Test 9: Command Words Always Interrupt
# ============================================================================

@pytest.mark.asyncio
async def test_command_words_always_interrupt(handler):
    """
    Scenario: Command words should always trigger interrupt when agent speaking
    Expected: Immediate interrupt
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    command_words = ['wait', 'stop', 'no', 'hold']
    
    for idx, cmd in enumerate(command_words, 1):
        event = TranscriptionEvent(
            transcript=cmd,
            confidence=0.8,
            is_final=True
        )
        
        should_interrupt = await handler.on_transcription_event(event)
        
        assert should_interrupt is True, f"Command word '{cmd}' should interrupt"
        assert handler.agent.speaking_stopped_count == idx


# ============================================================================
# Test 10: JSONL Logging Format
# ============================================================================

@pytest.mark.asyncio
async def test_jsonl_logging_format(handler, temp_log_file):
    """
    Scenario: Check that JSONL logs are properly formatted
    Expected: Valid JSON objects with all required fields
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    # Generate some events
    events = [
        ('uh', 0.8),
        ('wait', 0.9),
        ('umm okay', 0.7)
    ]
    
    for transcript, confidence in events:
        event = TranscriptionEvent(
            transcript=transcript,
            confidence=confidence,
            is_final=True
        )
        await handler.on_transcription_event(event)
    
    # Small delay to ensure writes complete
    await asyncio.sleep(0.2)
    
    # Read and validate log entries
    assert temp_log_file.exists(), "Log file should exist"
    
    with open(temp_log_file, 'r') as f:
        lines = f.readlines()
    
    assert len(lines) == 3, f"Should have 3 log entries, got {len(lines)}"
    
    for line in lines:
        data = json.loads(line)  # Should not raise
        
        # Check required fields
        required_fields = [
            'event_id', 'timestamp_iso', 'agent_speaking', 'transcript',
            'tokens', 'confidence', 'action', 'reason', 'duration_ms'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Validate data types
        assert isinstance(data['event_id'], str)
        assert isinstance(data['agent_speaking'], bool)
        assert isinstance(data['transcript'], str)
        assert isinstance(data['tokens'], list)
        assert isinstance(data['confidence'], (int, float))
        assert isinstance(data['action'], str)
        assert isinstance(data['reason'], str)
        assert isinstance(data['duration_ms'], (int, float))
        assert data['action'] in ['interrupt', 'ignore', 'register']


# ============================================================================
# Test 11: Thread Safety
# ============================================================================

@pytest.mark.asyncio
async def test_thread_safety_concurrent_events(handler):
    """
    Scenario: Multiple concurrent transcription events
    Expected: All handled correctly without race conditions
    """
    # Set agent to speaking state
    await handler.on_vad_state_change(is_speaking=True)
    
    # Create many concurrent events
    async def process_event(text, conf):
        event = TranscriptionEvent(transcript=text, confidence=conf)
        return await handler.on_transcription_event(event)
    
    tasks = []
    for i in range(50):
        if i % 2 == 0:
            tasks.append(process_event('uh', 0.8))
        else:
            tasks.append(process_event('wait', 0.8))
    
    results = await asyncio.gather(*tasks)
    
    # Check results
    expected_interrupts = 25  # Half are 'wait' commands
    actual_interrupts = sum(1 for r in results if r is True)
    
    assert actual_interrupts == expected_interrupts, \
        f"Expected {expected_interrupts} interrupts, got {actual_interrupts}"


# ============================================================================
# Test 12: Stats and Monitoring
# ============================================================================

def test_get_stats(handler):
    """
    Scenario: Request handler statistics
    Expected: Valid stats dictionary returned
    """
    stats = handler.get_stats()
    
    assert isinstance(stats, dict)
    assert 'agent_speaking' in stats
    assert 'ignored_words_count' in stats
    assert 'command_words_count' in stats
    assert 'confidence_threshold' in stats
    assert stats['ignored_words_count'] == 4  # From basic_config
    assert stats['command_words_count'] == 4  # From basic_config


# ============================================================================
# Test 13: Shutdown Gracefully
# ============================================================================

@pytest.mark.asyncio
async def test_shutdown_graceful(handler):
    """
    Scenario: Shutdown handler
    Expected: Clean shutdown without errors
    """
    # Process some events first
    await handler.on_vad_state_change(is_speaking=True)
    event = TranscriptionEvent(transcript='uh', confidence=0.8)
    await handler.on_transcription_event(event)
    
    # Should not raise
    await handler.shutdown()


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
