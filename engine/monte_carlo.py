"""Lognormal Monte Carlo utilities used by the geopolitical shock model."""

import math

import numpy as np


ITERATIONS = 1000


def simulate_lognormal(expected_shock, annual_volatility, duration_days, rng=None, iterations=ITERATIONS):
    """Return mean and the empirical central 95% interval for a lognormal shock."""
    if expected_shock <= 0:
        return {"expected": 0.0, "ci_low": 0.0, "ci_high": 0.0, "iterations": iterations}
    if annual_volatility < 0 or duration_days <= 0:
        raise ValueError("Volatility must be non-negative and duration must be positive.")

    generator = rng or np.random.default_rng()
    period_volatility = annual_volatility * math.sqrt(duration_days / 365.0)
    sigma_squared = math.log1p(period_volatility**2)
    sigma = math.sqrt(sigma_squared)
    # Parameterize the lognormal so its theoretical arithmetic mean equals expected_shock.
    mu = math.log(expected_shock) - sigma_squared / 2.0
    draws = generator.lognormal(mean=mu, sigma=sigma, size=iterations)
    low, high = np.percentile(draws, [2.5, 97.5])
    return {
        "expected": float(expected_shock),
        "ci_low": float(low),
        "ci_high": float(high),
        "iterations": iterations,
    }
