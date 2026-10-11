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


def simulate_correlated_lognormal(
    expected_shocks,
    annual_volatilities,
    duration_days,
    correlation_matrix,
    rng=None,
    iterations=ITERATIONS,
):
    """Sample correlated positive shocks with each requested arithmetic mean."""
    names = list(expected_shocks)
    if not names:
        return {}, np.empty((iterations, 0))
    if duration_days <= 0:
        raise ValueError("Duration must be positive.")

    expected = np.asarray([expected_shocks[name] for name in names], dtype=float)
    annual_volatility = np.asarray(
        [annual_volatilities[name] for name in names], dtype=float
    )
    correlation = np.asarray(correlation_matrix, dtype=float)
    expected_size = (len(names), len(names))
    if correlation.shape != expected_size:
        raise ValueError("Correlation matrix dimensions must match the shock series.")
    if np.any(annual_volatility < 0):
        raise ValueError("Volatility must be non-negative.")
    if not np.allclose(correlation, correlation.T):
        raise ValueError("Correlation matrix must be symmetric.")
    if not np.allclose(np.diag(correlation), 1.0):
        raise ValueError("Correlation matrix must have a unit diagonal.")
    if np.linalg.eigvalsh(correlation).min() < -1e-10:
        raise ValueError("Correlation matrix must be positive semidefinite.")
    if np.any(expected <= 0):
        raise ValueError("Expected shocks must be positive.")

    period_volatility = annual_volatility * math.sqrt(duration_days / 365.0)
    sigma_squared = np.log1p(period_volatility**2)
    sigma = np.sqrt(sigma_squared)
    covariance = correlation * np.outer(sigma, sigma)
    log_means = np.log(expected) - sigma_squared / 2.0
    generator = rng or np.random.default_rng()
    log_draws = generator.multivariate_normal(
        mean=log_means,
        cov=covariance,
        size=iterations,
        check_valid="raise",
    )
    draws = np.exp(log_draws)
    statistics = {}
    for index, name in enumerate(names):
        low, high = np.percentile(draws[:, index], [2.5, 97.5])
        statistics[name] = {
            "expected": float(expected[index]),
            "ci_low": float(low),
            "ci_high": float(high),
            "iterations": iterations,
        }
    return statistics, draws
