"""Exporter eligibility and per-commodity shock distributions."""

import hashlib

import numpy as np

from engine.chokepoint_engine import normalize_country
from engine.monte_carlo import simulate_correlated_lognormal
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
    candidates = {}

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
        raw_expected = (
            (combined_share / 100.0)
            * severity_multiplier
            * commodity["elasticity"]
        )
        alternative_exporters = {
            country: get_export_share_pct(country, export_share_key, knowledge_base)
            for country in commodity.get("alternative_exporters", [])
            if country not in country_ids
        }
        alternative_exporter_sources = {
            country: (
                f"FAOSTAT ({export_snapshot_metadata['reference_year']})"
                if load_export_record(country, export_share_key) is not None
                else "Illustrative knowledge-base assumption"
            )
            for country in alternative_exporters
        }
        alternative_supply_share = sum(alternative_exporters.values())
        substitution_relief = min(
            1.0,
            commodity.get("substitution_elasticity", 0.0)
            * alternative_supply_share
            / 100.0,
        )
        reserve_records = [
            knowledge_base.get("strategic_reserves", {})
            .get(country_id, {})
            .get(export_share_key, {})
            for country_id in country_ids
        ]
        reserve_record = max(
            reserve_records,
            key=lambda record: record.get("days_of_cover", 0.0),
            default={},
        )
        reserve_days = reserve_record.get("days_of_cover", 0.0)
        reserve_damping = min(1.0, reserve_days / duration_days) if reserve_days else 1.0
        expected_shock = raw_expected * (1.0 - substitution_relief) * reserve_damping
        realized_volatility = calculate_realized_volatility(commodity_id)
        annual_volatility = (
            realized_volatility["annualized_volatility"]
            if realized_volatility
            else commodity["annual_volatility"]
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
        candidates[commodity_id] = {
            "expected_shock": expected_shock,
            "raw_expected_shock": raw_expected,
            "substitution_relief": substitution_relief,
            "alternative_exporters": alternative_exporters,
            "alternative_exporter_sources": alternative_exporter_sources,
            "reserve_days": reserve_days,
            "reserve_damping": reserve_damping,
            "reserve_source_note": reserve_record.get("source_note"),
            "annual_volatility": annual_volatility,
            "metadata": {
                "name": commodity["name"],
                "export_share_pct": combined_share,
                "exporters": qualifying_exports,
                "exporter_data": exporter_data,
                "export_share_proxy": export_share_key if export_share_key != commodity_id else None,
                "elasticity": commodity["elasticity"],
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
            },
        }

    commodity_ids = list(candidates)
    correlation_matrix = np.eye(len(commodity_ids))
    indices = {commodity_id: index for index, commodity_id in enumerate(commodity_ids)}
    for group in knowledge_base.get("correlation_groups", {}).values():
        group_commodities = group["commodities"]
        group_matrix = np.asarray(group["correlation_matrix"], dtype=float)
        if group_matrix.shape != (len(group_commodities), len(group_commodities)):
            raise ValueError("Correlation-group matrix dimensions do not match its commodities.")
        for row, commodity_a in enumerate(group_commodities):
            for column, commodity_b in enumerate(group_commodities):
                if commodity_a in indices and commodity_b in indices:
                    correlation_matrix[indices[commodity_a], indices[commodity_b]] = (
                        group_matrix[row, column]
                    )

    monte_carlo_stats, _ = simulate_correlated_lognormal(
        {
            commodity_id: candidate["expected_shock"]
            for commodity_id, candidate in candidates.items()
        },
        {
            commodity_id: candidate["annual_volatility"]
            for commodity_id, candidate in candidates.items()
        },
        duration_days,
        correlation_matrix,
        rng=rng,
    )
    shocks = {
        commodity_id: {
            **monte_carlo_stats[commodity_id],
            **candidate["metadata"],
            "expected_before_substitution": candidate["raw_expected_shock"],
            "substitution_relief_pct": candidate["substitution_relief"] * 100,
            "alternative_exporters": candidate["alternative_exporters"],
            "alternative_exporter_sources": candidate["alternative_exporter_sources"],
            "reserve_days": candidate["reserve_days"],
            "reserve_damping": candidate["reserve_damping"],
            "reserve_source_note": candidate["reserve_source_note"],
            "annual_volatility": candidate["annual_volatility"],
        }
        for commodity_id, candidate in candidates.items()
    }
    return shocks
