import json
import unittest
from pathlib import Path

from engine.geopolitical import GeopoliticalEngine


ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ("United States", "China", "Russia", "India")


class KnowledgeBaseCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GeopoliticalEngine()
        cls.knowledge_base = cls.engine.knowledge_base
        cls.scenarios = []
        for country_id, country in cls.knowledge_base["countries"].items():
            for control in CONTROLS:
                control_id = control.casefold().replace(" ", "_")
                if country_id == control_id:
                    continue
                result = cls.engine.simulate_conflict(
                    country["name"], control, severity="high", duration_days=90
                )
                cls.scenarios.append(result)

    def test_every_modeled_country_has_a_nonempty_control_scenario(self):
        countries = {
            country_id: False
            for country_id in self.knowledge_base["countries"]
        }
        for result in self.scenarios:
            if result["affected_routes"] or result["price_shocks"]:
                for country_id in result["input_countries"]:
                    if country_id in countries:
                        countries[country_id] = True
        empty = [country for country, has_output in countries.items() if not has_output]
        self.assertEqual(empty, [])

    def test_every_knowledge_base_chokepoint_is_reachable(self):
        reached = {
            route["id"]
            for result in self.scenarios
            for route in result["affected_routes"]
        }
        expected = set(self.knowledge_base["chokepoints"])
        self.assertEqual(expected - reached, set())

    def test_every_knowledge_base_commodity_is_reachable(self):
        reached = {
            commodity
            for result in self.scenarios
            for commodity in result["price_shocks"]
        }
        expected = set(self.knowledge_base["commodities"])
        self.assertEqual(expected - reached, set())

    def test_all_knowledge_base_chokepoints_have_route_metadata(self):
        with (ROOT / "engine" / "knowledge_base.json").open(encoding="utf-8") as file:
            knowledge_base = json.load(file)
        for route_id, route in knowledge_base["chokepoints"].items():
            with self.subTest(chokepoint=route_id):
                self.assertTrue(route["origin_basins"])
                self.assertTrue(route["bordering_countries"])
                self.assertTrue(route["commodities"])


if __name__ == "__main__":
    unittest.main()
