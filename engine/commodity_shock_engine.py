"""Exporter eligibility and per-commodity shock distributions."""

import hashlib

import numpy as np

from engine.chokepoint_engine import normalize_country
from engine.monte_carlo import simulate_lognormal
from engine.source_data import (
    calculate_realized_volatility,
    load_export_record,
    load_export_snapshot_metadata,
    get_export_share_pct,
)


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
    export_snapshot_metadata = load_export_snapshot_metadata()
    shocks = {}

    for commodity_id, commodity in knowledge_base["commodities"].items():
        export_share_key = commodity.get("export_share_proxy", commodity_id)
        qualifying_exports = {}
        exporter_data = {}
        for country_id in country_ids:
            source_record = load_export_record(country_id, export_share_key)
            if source_record is not None:
                share = source_record["export_share_pct"]
                if source_record.get("net_importer") is True or share < MIN_EXPORT_SHARE:
                    continue
                qualifying_exports[country_id] = share
                exporter_data[country_id] = {
                    "source": "FAOSTAT",
                    "reference_year": export_snapshot_metadata["reference_year"],
                    "export_flag": source_record.get("export_flag"),
                    "net_importer": source_record.get("net_importer"),
                }
                continue

            share = get_export_share_pct(
                country_id, export_share_key, knowledge_base
            )
            if share >= MIN_EXPORT_SHARE:
                qualifying_exports[country_id] = share
                exporter_data[country_id] = {
                    "source": "Illustrative knowledge-base assumption",
                    "reference_year": None,
                    "export_flag": None,
                    "net_importer": None,
                }

        if not qualifying_exports:
            continue

        combined_share = sum(qualifying_exports.values())
        # Positive price impact is modeled as disrupted export share multiplied by elasticity.
        expected_shock = (combined_share / 100.0) * severity_multiplier * commodity["elasticity"]
        realized_volatility = calculate_realized_volatility(commodity_id)
        annual_volatility = (
            realized_volatility["annualized_volatility"]
            if realized_volatility
            else commodity["annual_volatility"]
        )
        stats = simulate_lognormal(
            expected_shock,
            annual_volatility,
            duration_days,
            rng=rng,
        )
        export_sources = {item["source"] for item in exporter_data.values()}
        if len(export_sources) == 1:
            export_data_source = next(iter(export_sources))
        else:
            export_data_source = "Mixed source snapshot and illustrative assumptions"
        if realized_volatility:
            volatility_source = (
                f"{realized_volatility['source']} {realized_volatility['series_id']} "
                f"({realized_volatility['start_date']} to {realized_volatility['end_date']})"
            )
        else:
            volatility_source = commodity["source_note"]
        shocks[commodity_id] = {
            **stats,
            "name": commodity["name"],
            "export_share_pct": combined_share,
            "exporters": qualifying_exports,
            "exporter_data": exporter_data,
            "export_share_proxy": export_share_key if export_share_key != commodity_id else None,
            "elasticity": commodity["elasticity"],
            "annual_volatility": annual_volatility,
            "pricing_horizon_hours": commodity.get("pricing_horizon_hours", 48),
            "volatility_source": volatility_source,
            "volatility_data": realized_volatility,
            "export_data_source": export_data_source,
            "export_data_year": (
                export_snapshot_metadata["reference_year"]
                if "FAOSTAT" in export_sources
                else None
            ),
            "chokepoints": commodity["chokepoints"],
        }
    return shocks
