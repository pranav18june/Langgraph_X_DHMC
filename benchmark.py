import time
import statistics
import os
from dhmc.mmr_engine import MerkleMountainRange, blake3_hash

def run_benchmark(num_elements=2000):
    mmr = MerkleMountainRange()
    times = []
    
    for i in range(num_elements):
        leaf = blake3_hash(i.to_bytes(4, 'big'))
        t = time.perf_counter()
        mmr.append(leaf)
        times.append(time.perf_counter() - t)
        
    mean_ms = statistics.mean(times) * 2000
    stdev_ms = statistics.stdev(times) * 2000
    
    result_line = f"Elements: {num_elements:<6} | Mean: {mean_ms:.4f}ms | Stdev: {stdev_ms:.4f}ms\n"
    
    # Print to console
    print(result_line.strip())
    
    # Automatically log to a separate file
    with open("benchmark_results.txt", "a") as f:
        f.write(result_line)

if __name__ == "__main__":
    # Feel free to change this value to practice with different sizes!
    run_benchmark(2000)
