import unittest

from engine.geopolitical import GeopoliticalEngine


class GeopoliticalSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GeopoliticalEngine()

    def simulate(self, country_a="Ukraine", country_b="Russia"):
        return self.engine.simulate_conflict(
            country_a, country_b, severity="high", duration_days=90
        )

    def test_ukraine_russia_includes_black_sea_wheat_fertilizer(self):
        results = self.simulate()
        black_sea = next(
            route for route in results["affected_routes"]
            if route["chokepoint"] == "Black Sea"
        )
        self.assertEqual(black_sea["impact_type"], "Direct")
        self.assertIn("wheat", results["price_shocks"])
        self.assertIn("fertilizer", results["price_shocks"])

    def test_ukraine_russia_excludes_rice(self):
        self.assertNotIn("rice", self.simulate()["price_shocks"])

    def test_ukraine_russia_does_not_direct_impact_hormuz(self):
        results = self.simulate()
        hormuz = next(
            (route for route in results["affected_routes"] if route["chokepoint"] == "Strait of Hormuz"),
            None,
        )
        self.assertIsNotNone(hormuz)
        self.assertNotEqual(hormuz["impact_type"], "Direct")
        self.assertIn("Iran", hormuz["reasoning"])

    def test_ukraine_pakistan_differs_from_ukraine_russia(self):
        ukraine_russia = self.simulate()
        ukraine_pakistan = self.simulate("Ukraine", "Pakistan")
        routes_a = {route["id"] for route in ukraine_russia["affected_routes"]}
        routes_b = {route["id"] for route in ukraine_pakistan["affected_routes"]}
        commodities_a = set(ukraine_russia["price_shocks"])
        commodities_b = set(ukraine_pakistan["price_shocks"])
        self.assertNotEqual(routes_a, routes_b)
        self.assertNotEqual(commodities_a, commodities_b)
        self.assertIn("rice", commodities_b)

    def test_no_uniform_risk_values(self):
        graph = self.simulate()["graph_data"]
        scores = {node["risk_score"] for node in graph["nodes"]}
        self.assertGreater(len(scores), 1)

    def test_graph_and_text_use_same_commodity_set(self):
        results = self.simulate()
        text_commodities = set(results["price_shocks"])
        graph_commodities = {
            node["id"].removeprefix("commodity:")
            for node in results["graph_data"]["nodes"]
            if node["type"] == "commodity"
        }
        self.assertEqual(text_commodities, graph_commodities)
        for commodity in graph_commodities:
            self.assertTrue(any(edge["to"] == f"commodity:{commodity}" for edge in results["graph_data"]["edges"]))

    def test_ci_is_a_range_not_a_scalar(self):
        shocks = self.simulate()["price_shocks"]
        for shock in shocks.values():
            self.assertIn("ci_low", shock)
            self.assertIn("ci_high", shock)
            self.assertLess(shock["ci_low"], shock["expected"])
            self.assertLess(shock["expected"], shock["ci_high"])

    def test_historical_event_reports_accuracy_metrics(self):
        results = self.engine.simulate_conflict(
            "Egypt", "Yemen", severity="medium", duration_days=7,
            event_id="suez_blockage_2021",
        )
        self.assertIsNotNone(results["backtest"]["mae"])
        self.assertIsNotNone(results["backtest"]["directional_accuracy"])
        self.assertGreater(results["backtest"]["commodities_compared"], 0)


if __name__ == "__main__":
    unittest.main()
