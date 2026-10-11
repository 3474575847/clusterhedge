"""Coordinates route exposure, exporter shocks, BOM impacts, and backtests."""

import json
from pathlib import Path

import numpy as np

from engine.bom_impact_engine import calculate_bom_impact
from engine.chokepoint_engine import (
    get_affected_chokepoints,
    get_escalation_chain,
    normalize_country,
)
from engine.commodity_shock_engine import calculate_commodity_shocks
from engine.graph_renderer import build_graph_data


KNOWLEDGE_BASE_PATH = Path(__file__).with_name("knowledge_base.json")
ALIASES = {
    "us": "united_states",
    "usa": "united_states",
    "america": "united_states",
    "uk": "united_kingdom",
    "uae": "united_arab_emirates",
    "congo": "democratic_republic_of_the_congo",
}


class GeopoliticalEngine:
    def __init__(self, knowledge_base_path=KNOWLEDGE_BASE_PATH):
        with open(knowledge_base_path, encoding="utf-8") as knowledge_file:
            self.knowledge_base = json.load(knowledge_file)
        self.choke_points = self.knowledge_base["chokepoints"]
        self.elasticity = {
            item["name"]: item["elasticity"]
            for item in self.knowledge_base["commodities"].values()
        }

    def _normalize(self, country):
        key = country.strip().casefold().replace("-", "_").replace(" ", "_")
        return ALIASES.get(key, normalize_country(country, self.knowledge_base))

    def get_affected_chokepoints(self, country_a, country_b, severity="high", duration_days=30):
        a, b = self._normalize(country_a), self._normalize(country_b)
        chain = get_escalation_chain(a, b, severity, self.knowledge_base)
        return get_affected_chokepoints(
            a, b, severity, duration_days, self.knowledge_base, chain
        )

    def simulate_conflict(self, country_a, country_b, severity="high", duration_days=30, event_id=None):
        if severity not in self.knowledge_base["severity_multipliers"]:
            raise ValueError(f"Unsupported severity: {severity}")
        if isinstance(duration_days, bool) or int(duration_days) <= 0:
            raise ValueError("Duration must be a positive number of days.")
        duration_days = int(duration_days)
        a, b = self._normalize(country_a), self._normalize(country_b)

        escalation_chain = get_escalation_chain(a, b, severity, self.knowledge_base)
        routes = get_affected_chokepoints(
            a,
            b,
            severity,
            duration_days,
            self.knowledge_base,
            escalation_chain,
        )
        price_shocks = calculate_commodity_shocks(
            a, b, severity, duration_days, self.knowledge_base
        )
        result = {
            "country_a": self.knowledge_base["countries"].get(a, {}).get("name", country_a.strip()),
            "country_b": self.knowledge_base["countries"].get(b, {}).get("name", country_b.strip()),
            "input_countries": [a, b],
            "severity": severity,
            "severity_multiplier": self.knowledge_base["severity_multipliers"][severity],
            "duration_days": duration_days,
            "affected_routes": routes,
            "escalation_chain": escalation_chain,
            "price_shocks": price_shocks,
        }
        result["graph_data"] = build_graph_data(result, self.knowledge_base)
        if event_id:
            result["backtest"] = self._compare_historical_event(event_id, price_shocks)
        return result

    def _compare_historical_event(self, event_id, price_shocks):
        event = self.knowledge_base["historical_events"].get(event_id)
        if not event:
            raise ValueError("Unknown historical event.")
        actual = event["actual_price_changes"]
        comparable = [
            (price_shocks[commodity]["expected"], actual_change)
            for commodity, actual_change in actual.items()
            if commodity in price_shocks
        ]
        if not comparable:
            metrics = {"mae": None, "directional_accuracy": None, "commodities_compared": 0}
        else:
            predicted = np.array([pair[0] for pair in comparable], dtype=float)
            observed = np.array([pair[1] for pair in comparable], dtype=float)
            metrics = {
                "mae": float(np.mean(np.abs(predicted - observed))),
                "directional_accuracy": float(
                    np.mean(np.sign(predicted) == np.sign(observed)) * 100.0
                ),
                "commodities_compared": len(comparable),
            }
        return {
            "event_id": event_id,
            "label": event["label"],
            "actual_price_changes": actual,
            **metrics,
        }

    def calculate_bom_impact(self, project, price_shocks):
        return calculate_bom_impact(project, price_shocks, self.knowledge_base)

    def generate_network_data(self, results, country_b=None):
        """Backward-compatible wrapper; new callers pass the computed result object."""
        if country_b is not None:
            results = self.simulate_conflict(results, country_b)
        return results["graph_data"]
