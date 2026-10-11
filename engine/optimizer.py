import random
import sys
from collections import defaultdict
from geopolitical import GeopoliticalEngine

def run_optimizer():
    eng = GeopoliticalEngine()
    countries = list(eng.country_weights.keys())
    
    n_sims = 100
    print(f"Running {n_sims} combinatorial conflict simulations...")
    print("-" * 50)
    
    # Track statistics
    shock_frequencies = defaultdict(int)
    avg_shocks = defaultdict(list)
    max_shocks = defaultdict(float)
    
    for i in range(1, n_sims + 1):
        a, b = random.sample(countries, 2)
        res = eng.simulate_conflict(a, b)
        
        # Track statistics
        for commodity, shock in res['price_shocks'].items():
            shock_frequencies[commodity] += 1
            avg_shocks[commodity].append(shock)
            max_shocks[commodity] = max(max_shocks[commodity], shock)
            
        # Print a few interesting samples
        if i <= 3:
            print(f"Sample {i}: {a.upper()} vs {b.upper()}")
            print(f"  Intensity: min(1.0, {eng.country_weights[a]} + {eng.country_weights[b]})")
            print(f"  Shocks: {res['price_shocks']}")
            print()
            
    print("-" * 50)
    print("Optimization & Evaluation Report")
    print("-" * 50)
    
    for commodity in max_shocks.keys():
        freq = shock_frequencies[commodity]
        avg = sum(avg_shocks[commodity]) / len(avg_shocks[commodity])
        mx = max_shocks[commodity]
        print(f"Commodity: {commodity:10} | Incidents: {freq:2d}/{n_sims} | Avg Shock: {avg*100:5.1f}% | Max Shock: {mx*100:5.1f}%")

if __name__ == '__main__':
    run_optimizer()
