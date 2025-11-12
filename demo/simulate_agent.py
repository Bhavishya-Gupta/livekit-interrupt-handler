"""
Demo simulation of LiveKit agent with InterruptHandler.

Simulates a conversation with various scenarios to demonstrate the handler's behavior.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from livekit_interrupt_handler import (
    InterruptHandler,
    TranscriptionEvent
)
from config import load_config


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class SimulatedAgent:
    """
    Simulates a LiveKit agent for demonstration purposes.
    """
    
    def __init__(self):
        self.is_speaking = False
        self.interrupted_count = 0
        self.speech_segments = []
    
    async def start_speaking(self, text: str):
        """Simulate agent starting to speak"""
        self.is_speaking = True
        self.speech_segments.append({
            'text': text,
            'started_at': datetime.now(),
            'completed': False
        })
        print(f"\n🤖 Agent: {text}")
        print(f"   [Agent is now SPEAKING]")
    
    async def stop_speaking(self):
        """Simulate agent being interrupted"""
        if self.is_speaking:
            self.is_speaking = False
            self.interrupted_count += 1
            if self.speech_segments:
                self.speech_segments[-1]['completed'] = False
            print(f"   ❌ [Agent INTERRUPTED - stopping speech]")
    
    async def finish_speaking(self):
        """Simulate agent naturally finishing speech"""
        if self.is_speaking:
            self.is_speaking = False
            if self.speech_segments:
                self.speech_segments[-1]['completed'] = True
            print(f"   ✅ [Agent FINISHED speaking]")


class ConversationSimulator:
    """
    Simulates a realistic conversation with interruptions.
    """
    
    def __init__(self):
        self.agent = SimulatedAgent()
        self.config = load_config()
        self.handler = InterruptHandler(self.agent, self.config)
        
        # Statistics
        self.total_events = 0
        self.interrupts = 0
        self.ignored = 0
        self.registered = 0
    
    async def simulate_user_speech(
        self, 
        transcript: str, 
        confidence: float = 0.8,
        delay_before: float = 0.5
    ):
        """
        Simulate user speaking with transcription.
        
        Args:
            transcript: What the user said
            confidence: ASR confidence score
            delay_before: Delay before this utterance (simulates timing)
        """
        await asyncio.sleep(delay_before)
        
        print(f"\n👤 User: \"{transcript}\" (confidence: {confidence:.2f})")
        
        event = TranscriptionEvent(
            transcript=transcript,
            confidence=confidence,
            is_final=True
        )
        
        self.total_events += 1
        should_interrupt = await self.handler.on_transcription_event(event)
        
        if should_interrupt:
            self.interrupts += 1
        else:
            if self.agent.is_speaking:
                self.ignored += 1
            else:
                self.registered += 1
        
        return should_interrupt
    
    async def run_scenario(self, name: str, steps: list):
        """
        Run a conversation scenario.
        
        Args:
            name: Scenario name
            steps: List of (action, *args) tuples
        """
        print("\n" + "=" * 70)
        print(f"SCENARIO: {name}")
        print("=" * 70)
        
        for step in steps:
            action = step[0]
            
            if action == 'agent_speak':
                await self.agent.start_speaking(step[1])
                await self.handler.on_vad_state_change(is_speaking=True)
                
            elif action == 'agent_finish':
                await self.agent.finish_speaking()
                await self.handler.on_vad_state_change(is_speaking=False)
                
            elif action == 'user_speak':
                await self.simulate_user_speech(*step[1:])
                
            elif action == 'delay':
                await asyncio.sleep(step[1])
        
        print()
    
    async def run_all_scenarios(self):
        """Run all demonstration scenarios"""
        
        # Scenario 1: Filler words while agent speaking
        await self.run_scenario(
            "Filler Words While Agent Speaking (Should Ignore)",
            [
                ('agent_speak', "Let me explain how our product works..."),
                ('user_speak', 'uh', 0.7, 0.3),
                ('user_speak', 'umm', 0.8, 0.2),
                ('user_speak', 'hmm', 0.75, 0.2),
                ('delay', 0.5),
                ('agent_finish',),
            ]
        )
        
        # Scenario 2: Real interruption while agent speaking
        await self.run_scenario(
            "Real Interruption While Agent Speaking (Should Stop)",
            [
                ('agent_speak', "Our pricing starts at just $99 per month..."),
                ('user_speak', 'wait one second', 0.85, 0.4),
                # Agent should be interrupted here
            ]
        )
        
        # Scenario 3: Filler while agent quiet
        await self.run_scenario(
            "Filler While Agent Quiet (Should Register)",
            [
                ('user_speak', 'umm', 0.8, 0.2),
                ('user_speak', 'uh', 0.75, 0.3),
                ('delay', 0.3),
            ]
        )
        
        # Scenario 4: Mixed filler and command
        await self.run_scenario(
            "Mixed Filler and Command (Should Stop)",
            [
                ('agent_speak', "The integration process takes about 2 weeks..."),
                ('user_speak', 'umm okay stop', 0.82, 0.4),
                # Agent should be interrupted here
            ]
        )
        
        # Scenario 5: Low confidence speech
        await self.run_scenario(
            "Low Confidence Background Noise (Should Ignore)",
            [
                ('agent_speak', "Let me show you the dashboard features..."),
                ('user_speak', 'hmm yeah', 0.15, 0.3),  # Low confidence
                ('user_speak', 'stop', 0.25, 0.2),      # Low confidence
                ('delay', 0.5),
                ('agent_finish',),
            ]
        )
        
        # Scenario 6: Command word (always interrupts)
        await self.run_scenario(
            "Command Word (Should Immediately Stop)",
            [
                ('agent_speak', "The enterprise plan includes..."),
                ('user_speak', 'wait', 0.9, 0.3),
                # Agent should be interrupted here
            ]
        )
        
        # Scenario 7: Natural conversation flow
        await self.run_scenario(
            "Natural Conversation Flow",
            [
                ('agent_speak', "Would you like to hear about our features?"),
                ('delay', 0.8),
                ('agent_finish',),
                ('user_speak', 'umm', 0.7, 0.2),      # User thinking
                ('user_speak', 'yes please', 0.85, 0.4),
                ('agent_speak', "Great! Our main features include..."),
                ('user_speak', 'uh huh', 0.7, 0.5),   # Filler - ignored
                ('delay', 0.5),
                ('agent_finish',),
                ('user_speak', 'sounds good', 0.88, 0.3),
            ]
        )
        
        # Scenario 8: False alarm then real interrupt
        await self.run_scenario(
            "False Alarm Then Real Interrupt",
            [
                ('agent_speak', "Let me walk you through the setup process..."),
                ('user_speak', 'hmm', 0.75, 0.3),     # Ignored
                ('user_speak', 'uh', 0.7, 0.2),       # Ignored
                ('user_speak', 'actually hold on', 0.88, 0.3),  # Real interrupt
                # Agent should stop on the last one
            ]
        )
    
    def print_summary(self):
        """Print execution summary"""
        print("\n" + "=" * 70)
        print("SIMULATION SUMMARY")
        print("=" * 70)
        print(f"Total transcription events: {self.total_events}")
        print(f"Interrupts triggered: {self.interrupts}")
        print(f"Events ignored (fillers while speaking): {self.ignored}")
        print(f"Events registered (speech while quiet): {self.registered}")
        print(f"\nAgent was interrupted {self.agent.interrupted_count} times")
        
        # Speech completion stats
        completed = sum(1 for s in self.agent.speech_segments if s.get('completed'))
        interrupted = len(self.agent.speech_segments) - completed
        print(f"Agent completed {completed} speech segments")
        print(f"Agent was cut off in {interrupted} speech segments")
        
        # Handler stats
        handler_stats = self.handler.get_stats()
        print(f"\nHandler Configuration:")
        print(f"  - Ignored words: {handler_stats['ignored_words_count']}")
        print(f"  - Command words: {handler_stats['command_words_count']}")
        print(f"  - Confidence threshold: {handler_stats['confidence_threshold']}")
        print(f"  - Log file: {handler_stats['log_file']}")
        print("=" * 70)
        
        # Expected vs actual validation
        print("\n✅ VALIDATION:")
        print(f"   Expected ~6-7 interrupts, got {self.interrupts}")
        print(f"   Expected ~5-7 ignored fillers, got {self.ignored}")
        print(f"   Expected ~3-4 registered speeches, got {self.registered}")
        
        if 5 <= self.interrupts <= 8 and 4 <= self.ignored <= 8:
            print("\n✅ All scenarios behaved as expected!")
        else:
            print("\n⚠️  Some scenarios may need review")


async def main():
    """Run the simulation"""
    print("\n" + "🎬 " * 20)
    print("LIVEKIT INTERRUPT HANDLER - INTERACTIVE DEMO")
    print("🎬 " * 20)
    
    simulator = ConversationSimulator()
    
    try:
        await simulator.run_all_scenarios()
        simulator.print_summary()
        
        print("\n📊 Check the log file for detailed JSONL event logs:")
        print(f"   {simulator.handler.log_file}")
        
        # Shutdown handler
        await simulator.handler.shutdown()
        
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user")
        await simulator.handler.shutdown()
    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
