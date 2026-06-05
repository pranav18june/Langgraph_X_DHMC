import time
import statistics
import gc
import os
from dhmc.mmr_engine import MerkleMountainRange
from dhmc.crypto import _blake3

def run_benchmark(num_elements=2000, runs=5, warmup_runs=2):
    print(f"--- Benchmark for {num_elements} elements ({runs} runs, {warmup_runs} warmups) ---")
    
    # Warmup
    for _ in range(warmup_runs):
        mmr = MerkleMountainRange()
        for i in range(num_elements):
            mmr.append(_blake3(i.to_bytes(4, 'big')))
            
    all_times = []
    
    gc.disable()
    try:
        for _ in range(runs):
            mmr = MerkleMountainRange()
            times = []
            for i in range(num_elements):
                leaf = _blake3(i.to_bytes(4, 'big'))
                t = time.perf_counter()
                mmr.append(leaf)
                times.append(time.perf_counter() - t)
            all_times.extend(times)
    finally:
        gc.enable()
        
    all_times.sort()
    mean_us = statistics.mean(all_times) * 1_000_000
    stdev_us = statistics.stdev(all_times) * 1_000_000
    
    p50_us = all_times[int(len(all_times) * 0.50)] * 1_000_000
    p95_us = all_times[int(len(all_times) * 0.95)] * 1_000_000
    p99_us = all_times[int(len(all_times) * 0.99)] * 1_000_000
    
    throughput = 1.0 / statistics.mean(all_times) if statistics.mean(all_times) > 0 else 0
    
    result_line = (f"Elements: {num_elements:<6} | "
                   f"Mean: {mean_us:.2f}μs | "
                   f"Stdev: {stdev_us:.2f}μs | "
                   f"p50: {p50_us:.2f}μs | "
                   f"p95: {p95_us:.2f}μs | "
                   f"p99: {p99_us:.2f}μs | "
                   f"Throughput: {throughput:,.0f} ops/sec\n")
    
    print(result_line.strip())
    
    with open("benchmark_results.txt", "a") as f:
        f.write(result_line)

if __name__ == "__main__":
    run_benchmark(1000)
    run_benchmark(2000)
