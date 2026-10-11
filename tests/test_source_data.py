import json
import unittest
from copy import deepcopy
from pathlib import Path

import numpy as np

from engine.commodity_shock_engine import calculate_commodity_shocks
from engine.geopolitical import GeopoliticalEngine
from engine.monte_carlo import simulate_correlated_lognormal
from engine.source_data import calculate_realized_volatility


ROOT = Path(__file__).resolve().parents[1]


class SourceBackedDataTests(unittest.TestCase):
    def setUp(self):
        self.engine = GeopoliticalEngine()
        with (ROOT / "engine" / "data_snapshots" / "faostat_exports.json").open(
            encoding="utf-8"
        ) as snapshot_file:
            self.export_snapshot = json.load(snapshot_file)

    def test_faostat_export_shares_override_static_wheat_shares(self):
        result = self.engine.simulate_conflict("Ukraine", "Russia", "high", 90)
        wheat = result["price_shocks"]["wheat"]
        snapshot = self.export_snapshot["commodities"]["wheat"]["countries"]
        expected_share = sum(
            snapshot[country]["export_share_pct"]
            for country in ("ukraine", "russia")
        )

        self.assertAlmostEqual(wheat["export_share_pct"], expected_share)
        self.assertEqual(wheat["export_data_source"], "FAOSTAT")
        self.assertEqual(
            wheat["export_data_year"],
            self.export_snapshot["metadata"]["reference_year"],
        )
        self.assertEqual(wheat["exporter_data"]["ukraine"]["export_flag"], "A")
        wheat_node = next(
            node for node in result["graph_data"]["nodes"]
            if node["id"] == "commodity:wheat"
        )
        self.assertIn("FAOSTAT", wheat_node["title"])
        self.assertIn("FRED", wheat_node["title"])

    def test_faostat_verified_net_importers_do_not_generate_rice_shock(self):
        countries = self.export_snapshot["commodities"]["rice"]["countries"]
        self.assertTrue(countries["ukraine"]["net_importer"])
        self.assertTrue(countries["russia"]["net_importer"])
        result = self.engine.simulate_conflict("Ukraine", "Russia", "high", 90)
        self.assertNotIn("rice", result["price_shocks"])

    def test_fred_price_snapshot_supplies_realized_volatility(self):
        result = calculate_realized_volatility("wheat")
        self.assertIsNotNone(result)
        self.assertGreater(result["annualized_volatility"], 0)
        self.assertEqual(result["series_id"], "PWHEAMTUSDM")
        self.assertGreaterEqual(result["observations"], 3)

    def test_uncovered_exports_are_labeled_illustrative(self):
        result = self.engine.simulate_conflict("Ukraine", "Russia", "high", 90)
        self.assertEqual(
            result["price_shocks"]["lpg"]["export_data_source"],
            "Illustrative knowledge-base assumption",
        )
        self.assertIsNone(result["price_shocks"]["lpg"]["export_data_year"])

    def test_correlated_shocks_widen_aggregate_confidence_interval(self):
        expected = {"wheat": 0.1, "corn": 0.08}
        volatility = {"wheat": 0.3, "corn": 0.25}
        independent, independent_draws = simulate_correlated_lognormal(
            expected,
            volatility,
            90,
            np.eye(2),
            rng=np.random.default_rng(77),
            iterations=10000,
        )
        correlated, correlated_draws = simulate_correlated_lognormal(
            expected,
            volatility,
            90,
            np.array([[1.0, 0.72], [0.72, 1.0]]),
            rng=np.random.default_rng(77),
            iterations=10000,
        )
        self.assertGreater(np.corrcoef(correlated_draws.T)[0, 1], 0.6)
        independent_width = np.diff(
            np.percentile(independent_draws.sum(axis=1), [2.5, 97.5])
        )[0]
        correlated_width = np.diff(
            np.percentile(correlated_draws.sum(axis=1), [2.5, 97.5])
        )[0]
        self.assertGreater(correlated_width, independent_width)
        self.assertLess(correlated["wheat"]["ci_low"], correlated["wheat"]["ci_high"])
        self.assertLess(independent["corn"]["ci_low"], independent["corn"]["ci_high"])

    def test_rice_substitution_dampens_india_pakistan_shock(self):
        knowledge_base = deepcopy(self.engine.knowledge_base)
        with_alternatives = calculate_commodity_shocks(
            "india", "pakistan", "high", 90, knowledge_base
        )["rice"]
        knowledge_base["commodities"]["rice"]["alternative_exporters"] = []
        without_alternatives = calculate_commodity_shocks(
            "india", "pakistan", "high", 90, knowledge_base
        )["rice"]

        self.assertLess(with_alternatives["expected"], without_alternatives["expected"])
        self.assertGreater(
            without_alternatives["expected_before_substitution"],
            with_alternatives["expected"],
        )
        self.assertGreater(with_alternatives["substitution_relief_pct"], 0)
        self.assertEqual(without_alternatives["substitution_relief_pct"], 0)

    def test_spr_dampens_oil_shock(self):
        knowledge_base = deepcopy(self.engine.knowledge_base)
        with_reserve = calculate_commodity_shocks(
            "United States", "Russia", "high", 90, knowledge_base
        )["crude_oil"]
        knowledge_base["strategic_reserves"] = {}
        without_reserve = calculate_commodity_shocks(
            "United States", "Russia", "high", 90, knowledge_base
        )["crude_oil"]

        self.assertLess(with_reserve["expected"], without_reserve["expected"])
        self.assertEqual(with_reserve["reserve_damping"], 40 / 90)
        self.assertEqual(with_reserve["reserve_days"], 40)


if __name__ == "__main__":
    unittest.main()
