import json
import unittest
from pathlib import Path

from engine.geopolitical import GeopoliticalEngine
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


if __name__ == "__main__":
    unittest.main()
