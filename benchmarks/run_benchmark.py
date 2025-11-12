"""
Performance benchmarks for LiveKit Interrupt Handler.

Measures processing latency, throughput, and resource usage.
"""

import asyncio
import sys
import time
import statistics
from pathlib import Path
from datetime import datetime
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

from livekit_interrupt_handler import InterruptHandler, TranscriptionEvent


class MockAgent:
    """Lightweight mock agent for benchmarking"""
    async def stop_speaking(self):
        pass


class BenchmarkRunner:
    """Runs performance benchmarks"""
    
    def __init__(self):
        self.results = {}
    
    async def benchmark_single_event_latency(self, iterations=1000):
        """
        Measure latency of processing a single transcription event.
        
        Target: < 5ms per event
        """
        print(f"\n📊 Benchmark 1: Single Event Latency ({iterations} iterations)")
        print("-" * 60)
        
        with tempfile.NamedTemporaryFile(suffix='.jsonl') as f:
            config = {
                'ignored_words': ['uh', 'umm', 'hmm'],
                'command_words': ['wait', 'stop', 'no'],
                'confidence_threshold': 0.3,
                'low_confidence_time_ms': 500,
                'log_file': f.name,
                'enable_logging': False  # Disable to measure pure logic
            }
            
            agent = MockAgent()
            handler = InterruptHandler(agent, config)
            await handler.on_vad_state_change(is_speaking=True)
            
            latencies = []
            
            for i in range(iterations):
                event = TranscriptionEvent(
                    transcript='uh' if i % 2 == 0 else 'wait please',
                    confidence=0.8
                )
                
                start = time.perf_counter()
                await handler.on_transcription_event(event)
                end = time.perf_counter()
                
                latencies.append((end - start) * 1000)  # Convert to ms
            
            await handler.shutdown()
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        max_latency = max(latencies)
        
        print(f"Average latency:  {avg_latency:.3f} ms")
        print(f"Median latency:   {median_latency:.3f} ms")
        print(f"P95 latency:      {p95_latency:.3f} ms")
        print(f"P99 latency:      {p99_latency:.3f} ms")
        print(f"Max latency:      {max_latency:.3f} ms")
        
        # Validate against target
        target_ms = 5.0
        if avg_latency < target_ms:
            print(f"✅ PASS: Average latency {avg_latency:.3f}ms < {target_ms}ms")
        else:
            print(f"❌ FAIL: Average latency {avg_latency:.3f}ms >= {target_ms}ms")
        
        self.results['single_event_latency'] = {
            'avg_ms': avg_latency,
            'median_ms': median_latency,
            'p95_ms': p95_latency,
            'p99_ms': p99_latency,
            'max_ms': max_latency,
            'passed': avg_latency < target_ms
        }
        
        return avg_latency < target_ms
    
    async def benchmark_concurrent_throughput(self, concurrent=100, batches=10):
        """
        Measure throughput under concurrent load.
        
        Target: > 500 events/second
        """
        print(f"\n📊 Benchmark 2: Concurrent Throughput")
        print(f"    ({concurrent} concurrent events × {batches} batches)")
        print("-" * 60)
        
        with tempfile.NamedTemporaryFile(suffix='.jsonl') as f:
            config = {
                'ignored_words': ['uh', 'umm', 'hmm'],
                'command_words': ['wait', 'stop', 'no'],
                'confidence_threshold': 0.3,
                'low_confidence_time_ms': 500,
                'log_file': f.name,
                'enable_logging': False
            }
            
            agent = MockAgent()
            handler = InterruptHandler(agent, config)
            await handler.on_vad_state_change(is_speaking=True)
            
            total_events = 0
            total_time = 0
            
            for batch in range(batches):
                tasks = []
                
                for i in range(concurrent):
                    event = TranscriptionEvent(
                        transcript='uh' if i % 2 == 0 else 'stop now',
                        confidence=0.8
                    )
                    tasks.append(handler.on_transcription_event(event))
                
                start = time.perf_counter()
                await asyncio.gather(*tasks)
                end = time.perf_counter()
                
                batch_time = end - start
                total_events += concurrent
                total_time += batch_time
            
            await handler.shutdown()
        
        # Calculate throughput
        throughput = total_events / total_time
        avg_batch_time = (total_time / batches) * 1000  # ms
        
        print(f"Total events processed: {total_events}")
        print(f"Total time:            {total_time:.3f} seconds")
        print(f"Throughput:            {throughput:.1f} events/second")
        print(f"Avg batch time:        {avg_batch_time:.3f} ms")
        
        # Validate against target
        target_throughput = 500
        if throughput > target_throughput:
            print(f"✅ PASS: Throughput {throughput:.1f} > {target_throughput} events/s")
        else:
            print(f"❌ FAIL: Throughput {throughput:.1f} <= {target_throughput} events/s")
        
        self.results['concurrent_throughput'] = {
            'throughput_eps': throughput,
            'avg_batch_ms': avg_batch_time,
            'passed': throughput > target_throughput
        }
        
        return throughput > target_throughput
    
    async def benchmark_state_change_overhead(self, iterations=10000):
        """
        Measure overhead of VAD state changes.
        
        Target: < 0.1ms per state change
        """
        print(f"\n📊 Benchmark 3: VAD State Change Overhead ({iterations} iterations)")
        print("-" * 60)
        
        with tempfile.NamedTemporaryFile(suffix='.jsonl') as f:
            config = {
                'ignored_words': ['uh'],
                'command_words': ['wait'],
                'confidence_threshold': 0.3,
                'low_confidence_time_ms': 500,
                'log_file': f.name,
                'enable_logging': False
            }
            
            agent = MockAgent()
            handler = InterruptHandler(agent, config)
            
            latencies = []
            
            for i in range(iterations):
                is_speaking = i % 2 == 0
                
                start = time.perf_counter()
                await handler.on_vad_state_change(is_speaking)
                end = time.perf_counter()
                
                latencies.append((end - start) * 1000)
            
            await handler.shutdown()
        
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        
        print(f"Average latency: {avg_latency:.4f} ms")
        print(f"Max latency:     {max_latency:.4f} ms")
        
        target_ms = 0.1
        if avg_latency < target_ms:
            print(f"✅ PASS: State change overhead {avg_latency:.4f}ms < {target_ms}ms")
        else:
            print(f"❌ FAIL: State change overhead {avg_latency:.4f}ms >= {target_ms}ms")
        
        self.results['state_change_overhead'] = {
            'avg_ms': avg_latency,
            'max_ms': max_latency,
            'passed': avg_latency < target_ms
        }
        
        return avg_latency < target_ms
    
    async def benchmark_word_list_update(self, iterations=1000):
        """
        Measure latency of dynamic word list updates.
        
        Target: < 1ms per update
        """
        print(f"\n📊 Benchmark 4: Dynamic Word List Update ({iterations} iterations)")
        print("-" * 60)
        
        with tempfile.NamedTemporaryFile(suffix='.jsonl') as f:
            config = {
                'ignored_words': ['uh'],
                'command_words': ['wait'],
                'confidence_threshold': 0.3,
                'low_confidence_time_ms': 500,
                'log_file': f.name,
                'enable_logging': False
            }
            
            agent = MockAgent()
            handler = InterruptHandler(agent, config)
            
            latencies = []
            
            for i in range(iterations):
                words = ['uh', 'umm', 'hmm', 'haan', 'er', 'ah'][:((i % 6) + 1)]
                
                start = time.perf_counter()
                handler.update_ignored_words(words)
                end = time.perf_counter()
                
                latencies.append((end - start) * 1000)
            
            await handler.shutdown()
        
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        
        print(f"Average latency: {avg_latency:.4f} ms")
        print(f"Max latency:     {max_latency:.4f} ms")
        
        target_ms = 1.0
        if avg_latency < target_ms:
            print(f"✅ PASS: Update latency {avg_latency:.4f}ms < {target_ms}ms")
        else:
            print(f"❌ FAIL: Update latency {avg_latency:.4f}ms >= {target_ms}ms")
        
        self.results['word_list_update'] = {
            'avg_ms': avg_latency,
            'max_ms': max_latency,
            'passed': avg_latency < target_ms
        }
        
        return avg_latency < target_ms
    
    async def benchmark_with_logging(self, events=1000):
        """
        Measure impact of JSONL logging on performance.
        
        Target: < 2x overhead with logging enabled
        """
        print(f"\n📊 Benchmark 5: Logging Overhead ({events} events)")
        print("-" * 60)
        
        # Benchmark without logging
        with tempfile.NamedTemporaryFile(suffix='.jsonl') as f:
            config = {
                'ignored_words': ['uh'],
                'command_words': ['wait'],
                'confidence_threshold': 0.3,
                'low_confidence_time_ms': 500,
                'log_file': f.name,
                'enable_logging': False
            }
            
            agent = MockAgent()
            handler = InterruptHandler(agent, config)
            await handler.on_vad_state_change(is_speaking=True)
            
            start = time.perf_counter()
            for i in range(events):
                event = TranscriptionEvent(transcript='uh', confidence=0.8)
                await handler.on_transcription_event(event)
            no_log_time = time.perf_counter() - start
            
            await handler.shutdown()
        
        # Benchmark with logging
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            config['enable_logging'] = True
            config['log_file'] = str(log_path)
            
            agent = MockAgent()
            handler = InterruptHandler(agent, config)
            await handler.on_vad_state_change(is_speaking=True)
            
            start = time.perf_counter()
            for i in range(events):
                event = TranscriptionEvent(transcript='uh', confidence=0.8)
                await handler.on_transcription_event(event)
            with_log_time = time.perf_counter() - start
            
            await handler.shutdown()
            
            # Wait for writes to complete
            await asyncio.sleep(0.2)
        finally:
            if log_path.exists():
                log_path.unlink()
        
        overhead = (with_log_time / no_log_time)
        
        print(f"Without logging: {no_log_time:.3f} seconds ({events/no_log_time:.1f} eps)")
        print(f"With logging:    {with_log_time:.3f} seconds ({events/with_log_time:.1f} eps)")
        print(f"Overhead factor: {overhead:.2f}x")
        
        target_overhead = 2.0
        if overhead < target_overhead:
            print(f"✅ PASS: Logging overhead {overhead:.2f}x < {target_overhead}x")
        else:
            print(f"❌ FAIL: Logging overhead {overhead:.2f}x >= {target_overhead}x")
        
        self.results['logging_overhead'] = {
            'no_log_seconds': no_log_time,
            'with_log_seconds': with_log_time,
            'overhead_factor': overhead,
            'passed': overhead < target_overhead
        }
        
        return overhead < target_overhead
    
    def print_summary(self):
        """Print overall benchmark summary"""
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        
        all_passed = all(r['passed'] for r in self.results.values())
        
        for name, result in self.results.items():
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"{status} - {name}")
        
        print("=" * 60)
        
        if all_passed:
            print("✅ All benchmarks PASSED!")
            print("   Handler meets real-time performance requirements.")
        else:
            print("⚠️  Some benchmarks FAILED")
            print("   Review failed tests and optimize if needed.")
        
        return all_passed


async def main():
    """Run all benchmarks"""
    print("\n" + "⚡ " * 20)
    print("LIVEKIT INTERRUPT HANDLER - PERFORMANCE BENCHMARKS")
    print("⚡ " * 20)
    
    runner = BenchmarkRunner()
    
    try:
        await runner.benchmark_single_event_latency()
        await runner.benchmark_concurrent_throughput()
        await runner.benchmark_state_change_overhead()
        await runner.benchmark_word_list_update()
        await runner.benchmark_with_logging()
        
        all_passed = runner.print_summary()
        
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"\n❌ Benchmark error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
