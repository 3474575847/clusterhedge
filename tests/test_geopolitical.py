import unittest

from engine.geopolitical import GeopoliticalEngine, run_simulation


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

    def test_ukraine_russia_steel_export_share_is_9_5_percent(self):
        countries = self.engine.knowledge_base["countries"]
        combined_share = (
            countries["ukraine"]["exports"]["steel"]
            + countries["russia"]["exports"]["steel"]
        )
        self.assertEqual(combined_share, 9.5)

    def test_ukraine_russia_excludes_panama_canal(self):
        routes = {route["chokepoint"] for route in self.simulate()["affected_routes"]}
        self.assertNotIn("Panama Canal", routes)

    def test_ukraine_russia_uses_malacca_for_exporter_route_flow(self):
        routes = {route["chokepoint"] for route in self.simulate()["affected_routes"]}
        self.assertIn("Strait of Malacca", routes)

    def test_ukraine_russia_excludes_taiwan_strait_crude_oil_edge(self):
        graph = self.simulate()["graph_data"]
        self.assertFalse(any(
            edge["from"] == "chokepoint:taiwan_strait"
            and edge["to"] == "commodity:crude_oil"
            for edge in graph["edges"]
        ))

    def test_ukraine_russia_does_not_direct_impact_hormuz(self):
        results = self.simulate()
        hormuz = next(
            (route for route in results["affected_routes"] if route["chokepoint"] == "Strait of Hormuz"),
            None,
        )
        self.assertTrue(hormuz is None or hormuz["impact_type"] != "Direct")

    def test_ukraine_russia_excludes_hormuz_and_asian_straits(self):
        routes = {route["chokepoint"] for route in self.simulate()["affected_routes"]}
        self.assertNotIn("Strait of Hormuz", routes)
        self.assertNotIn("Taiwan Strait", routes)
        self.assertNotIn("South China Sea", routes)

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

    def test_india_pakistan_excludes_india_fertilizer_export_shock(self):
        results = self.simulate("India", "Pakistan")
        self.assertNotIn("fertilizer", results["price_shocks"])
        exposure = next(
            item for item in results["import_cost_exposures"]
            if item["country"] == "India" and item["commodity"] == "fertilizer"
        )
        self.assertEqual(exposure["status"], "unavailable")

    def test_india_pakistan_includes_bay_of_bengal(self):
        results = self.simulate("India", "Pakistan")
        routes = {route["chokepoint"] for route in results["affected_routes"]}
        self.assertEqual(
            routes,
            {"Bay of Bengal", "Indus & Arabian Sea Ports", "Strait of Malacca"},
        )

    def test_india_pakistan_escalation_chain_is_symmetric(self):
        results = self.simulate("India", "Pakistan")
        india_partners = {
            link["to"] for link in results["escalation_chain"]
            if link["from"] == "india"
        }
        self.assertTrue(
            {"united_states", "russia", "france", "japan"}.issubset(india_partners)
        )

    def test_no_uniform_risk_values(self):
        graph = self.simulate()["graph_data"]
        scores = {node["risk_score"] for node in graph["nodes"]}
        self.assertGreater(len(scores), 1)

    def test_third_party_risk_is_damped_below_primary_risk(self):
        nodes = {
            node["id"]: node["risk_score"]
            for node in self.simulate()["graph_data"]["nodes"]
        }
        self.assertLess(nodes["country:iran"], nodes["country:russia"])
        self.assertLess(nodes["country:china"], nodes["country:russia"])
        hormuz = next(
            (
                route for route in self.simulate()["affected_routes"]
                if route["chokepoint"] == "Strait of Hormuz"
            ),
            None,
        )
        self.assertTrue(hormuz is None or hormuz["magnitude"] <= 0.15)

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

    def test_graph_has_hierarchical_layers_and_distinct_partner_colors(self):
        graph = self.simulate()["graph_data"]
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(nodes["country:ukraine"]["level"], 0)
        self.assertEqual(nodes["chokepoint:black_sea"]["level"], 2)
        self.assertEqual(nodes["commodity:wheat"]["level"], 3)
        self.assertNotEqual(
            nodes["country:belarus"]["color"],
            nodes["country:china"]["color"],
        )

    def test_graph_hides_chokepoints_without_commodity_edges(self):
        graph = self.simulate()["graph_data"]
        commodities = {
            edge["from"] for edge in graph["edges"]
            if edge["from"].startswith("chokepoint:")
            and edge["to"].startswith("commodity:")
        }
        chokepoint_nodes = {
            node["id"] for node in graph["nodes"]
            if node["type"] == "chokepoint"
        }
        self.assertEqual(chokepoint_nodes, commodities)

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

    def test_module_run_simulation_exposes_requested_result_keys(self):
        results = run_simulation("Ukraine", "Russia", "high", 90)
        self.assertIn("Black Sea", results["chokepoints"])
        self.assertIn("Wheat", results["commodities"])


if __name__ == "__main__":
    unittest.main()
