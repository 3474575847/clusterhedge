import re
import unittest
from pathlib import Path

from engine.geopolitical import run_simulation


KNOWN_PAIRS = [
    ("Ukraine", "Russia"),
    ("India", "Pakistan"),
    ("Iran", "USA"),
    ("China", "Taiwan"),
    ("Israel", "Iran"),
]
ROOT = Path(__file__).resolve().parents[1]


class GeopoliticalInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {
            pair: run_simulation(*pair, "high", 90)
            for pair in KNOWN_PAIRS
        }

    def test_no_uniform_risk_values(self):
        for (country_a, country_b), result in self.results.items():
            risks = [node["risk_score"] for node in result["graph_data"]["nodes"]]
            self.assertGreater(
                len(set(risks)),
                1,
                f"{country_a} vs {country_b}: all graph risks are identical",
            )

    def test_all_confidence_intervals_are_ranges(self):
        for (country_a, country_b), result in self.results.items():
            for commodity, shock in result["price_shocks"].items():
                display = f"+{shock['ci_low'] * 100:.1f}% to +{shock['ci_high'] * 100:.1f}%"
                self.assertRegex(
                    display,
                    re.compile(r" to "),
                    f"{country_a} vs {country_b}: {commodity} interval is not a range",
                )
                self.assertLess(shock["ci_low"], shock["ci_high"])

    def test_primary_conflict_risks_are_not_below_all_third_parties(self):
        for (country_a, country_b), result in self.results.items():
            risks = {
                node["id"].removeprefix("country:"): node["risk_score"]
                for node in result["graph_data"]["nodes"]
                if node["type"] in {
                    "conflict_country",
                    "ally_country",
                    "partner_country",
                    "adversary_country",
                }
            }
            primary = [
                risks.get(result["input_countries"][0], 0.0),
                risks.get(result["input_countries"][1], 0.0),
            ]
            third_party = [
                risk for country, risk in risks.items()
                if country not in result["input_countries"]
            ]
            self.assertGreaterEqual(
                min(primary),
                max(third_party, default=0.0),
                f"{country_a} vs {country_b}: a third party outranks a primary country",
            )

    def test_graph_and_text_commodity_sets_match(self):
        for (country_a, country_b), result in self.results.items():
            text = set(result["price_shocks"])
            graph = {
                node["id"].removeprefix("commodity:")
                for node in result["graph_data"]["nodes"]
                if node["type"] == "commodity"
            }
            self.assertEqual(text, graph, f"{country_a} vs {country_b}")

    def test_engine_does_not_embed_country_specific_policy_data(self):
        forbidden = ('"ukraine"', '"russia"', '"india"', '"pakistan"', '"iran"', '"china"')
        for path in (ROOT / "engine").glob("*.py"):
            source = path.read_text(encoding="utf-8").lower()
            for country_literal in forbidden:
                self.assertNotIn(
                    country_literal,
                    source,
                    f"{path.name} hardcodes country-specific behavior",
                )

    def test_uncovered_country_is_explicitly_flagged(self):
        result = run_simulation("Israel", "Iran", "high", 90)
        self.assertTrue(result["coverage_warnings"])
        self.assertIn("Israel", result["coverage_warnings"][0])
        self.assertTrue(result["price_shocks"] or result["affected_routes"])


if __name__ == "__main__":
    unittest.main()
