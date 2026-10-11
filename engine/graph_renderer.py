"""Build vis-network data from the already-computed simulation result."""

import logging


logger = logging.getLogger(__name__)

ROLE_COLORS = {
    "conflict_country": "#ef4444",
    "ally_country": "#f97316",
    "partner_country": "#f97316",
    "adversary_country": "#64748b",
    "chokepoint": "#fbbf24",
    "commodity": "#38bdf8",
}


def build_graph_data(results, knowledge_base):
    """Render the same route and commodity objects used by the text and BOM views."""
    nodes = []
    edges = []
    node_ids = set()
    shock_by_id = results["price_shocks"]

    def add_node(node_id, label, role, risk_score, tooltip):
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({
            "id": node_id,
            "label": f"{label}\nRisk: {risk_score:.1f}",
            "title": tooltip,
            "type": role,
            "risk_score": round(risk_score, 1),
            "color": ROLE_COLORS[role],
            "shape": "dot",
        })

    def add_edge(source, target, label, weight=1.0):
        edges.append({
            "from": source,
            "to": target,
            "label": label,
            "width": max(1.0, min(5.0, weight * 4.0)),
            "title": label,
        })

    inputs = results["input_countries"]
    for country_id in inputs:
        country = knowledge_base["countries"].get(country_id, {"name": country_id.title()})
        share = sum(shock["exporters"].get(country_id, 0.0) for shock in shock_by_id.values())
        score = share * results["severity_multiplier"]
        tooltip = f"Conflict country: {country['name']}. Export-risk score: {score:.1f}."
        add_node(f"country:{country_id}", country["name"], "conflict_country", score, tooltip)

    relation_types = {}
    for escalation in results["escalation_chain"]:
        target = escalation["to"]
        relation_types[target] = escalation["relation"]
        country = knowledge_base["countries"].get(target, {"name": target.title()})
        source_name = knowledge_base["countries"].get(escalation["from"], {}).get("name", escalation["from"])
        relation_role = f"{escalation['relation']}_country"
        score = max(
            (route["magnitude"] * 100 for route in results["affected_routes"] if target in route["linked_countries"]),
            default=results["severity_multiplier"] * 25,
        )
        tooltip = f"{escalation['relation'].title()} escalation from {source_name}: {escalation['reason']}"
        add_node(f"country:{target}", country["name"], relation_role, score, tooltip)
        add_edge(
            f"country:{escalation['from']}",
            f"country:{target}",
            f"{escalation['relation']}: escalation",
            results["severity_multiplier"],
        )

    for route in results["affected_routes"]:
        route_id = f"chokepoint:{route['id']}"
        tooltip = (
            f"{route['impact_type']} impact. Magnitude: {route['magnitude'] * 100:.1f}%. "
            f"Reason: {route['reasoning']}"
        )
        add_node(route_id, route["chokepoint"], "chokepoint", route["magnitude"] * 100, tooltip)
        connected = [
            country for country in route["linked_countries"]
            if f"country:{country}" in node_ids
        ]
        for country in connected:
            add_edge(
                f"country:{country}",
                route_id,
                route["impact_type"],
                route["magnitude"],
            )

    for commodity_id, shock in shock_by_id.items():
        name = shock["name"]
        risk = shock["expected"] * 100
        ci = f"+{shock['ci_low'] * 100:.1f}% to +{shock['ci_high'] * 100:.1f}%"
        exporters = ", ".join(
            f"{knowledge_base['countries'].get(country, {}).get('name', country)} {share:.1f}%"
            for country, share in shock["exporters"].items()
        )
        tooltip = (
            f"Expected: +{risk:.1f}%. 95% CI: {ci}. "
            f"Export shares: {exporters}. Source: {shock['volatility_source']}"
        )
        commodity_node = f"commodity:{commodity_id}"
        add_node(commodity_node, name, "commodity", risk, tooltip)

        routed = False
        for route in results["affected_routes"]:
            if commodity_id not in route["commodities"]:
                continue
            route_node = f"chokepoint:{route['id']}"
            if route_node in node_ids:
                add_edge(route_node, commodity_node, f"shock: +{risk:.1f}%", shock["expected"])
                routed = True

        # A sourced commodity remains connected even if no exposed route carries it.
        if not routed:
            for country_id, share in shock["exporters"].items():
                country_node = f"country:{country_id}"
                if country_node in node_ids:
                    add_edge(country_node, commodity_node, f"exports: {share:.1f}%", share / 100)

    repeated_risks = {}
    for node in nodes:
        rounded = node["risk_score"]
        repeated_risks.setdefault(rounded, []).append(node["id"])
    duplicates = {risk: ids for risk, ids in repeated_risks.items() if len(ids) > 1}
    if duplicates:
        logger.warning("Repeated graph risk scores detected: %s", duplicates)

    return {"nodes": nodes, "edges": edges}
