"""Exporter eligibility and per-commodity shock distributions."""

import hashlib

import numpy as np

from engine.chokepoint_engine import normalize_country
from engine.monte_carlo import simulate_lognormal


MIN_EXPORT_SHARE = 2.0


def calculate_commodity_shocks(country_a, country_b, severity, duration_days, knowledge_base):
    country_ids = [
        normalize_country(country_a, knowledge_base),
        normalize_country(country_b, knowledge_base),
    ]
    seed_source = f"{'|'.join(sorted(country_ids))}|{severity}|{duration_days}"
    seed = int(hashlib.sha256(seed_source.encode("utf-8")).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    severity_multiplier = knowledge_base["severity_multipliers"][severity]
    shocks = {}

    for commodity_id, commodity in knowledge_base["commodities"].items():
        export_share_key = commodity.get("export_share_proxy", commodity_id)
        qualifying_exports = {
            country_id: knowledge_base["countries"].get(country_id, {}).get("exports", {}).get(export_share_key, 0.0)
            for country_id in country_ids
        }
        qualifying_exports = {
            country_id: share for country_id, share in qualifying_exports.items()
            if share >= MIN_EXPORT_SHARE
        }
        if not qualifying_exports:
            continue

        combined_share = sum(qualifying_exports.values())
        # Positive price impact is modeled as disrupted export share multiplied by elasticity.
        expected_shock = (combined_share / 100.0) * severity_multiplier * commodity["elasticity"]
        stats = simulate_lognormal(
            expected_shock,
            commodity["annual_volatility"],
            duration_days,
            rng=rng,
        )
        shocks[commodity_id] = {
            **stats,
            "name": commodity["name"],
            "export_share_pct": combined_share,
            "exporters": qualifying_exports,
            "export_share_proxy": export_share_key if export_share_key != commodity_id else None,
            "elasticity": commodity["elasticity"],
            "annual_volatility": commodity["annual_volatility"],
            "pricing_horizon_hours": commodity.get("pricing_horizon_hours", 48),
            "volatility_source": commodity["source_note"],
            "chokepoints": commodity["chokepoints"],
        }
    return shocks
