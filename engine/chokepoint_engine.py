"""Data-driven route exposure classification."""

import math

from engine.source_data import get_export_share_pct


ALLIANCE_RELATIONS = {"ally", "partner"}
SPILLOVER_THRESHOLD = 5.0
DIRECT_EXPORT_THRESHOLD = 15.0


def normalize_country(value, knowledge_base):
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    for country_id, data in knowledge_base["countries"].items():
        if normalized in {country_id.casefold(), data["name"].casefold().replace(" ", "_")}:
            return country_id
    return normalized


def get_escalation_chain(country_a, country_b, severity, knowledge_base):
    """Return explicit, one-hop ally/partner links only at medium severity or above."""
    if knowledge_base["severity_multipliers"][severity] < knowledge_base["severity_multipliers"]["medium"]:
        return []

    participants = {country_a, country_b}
    chain = []
    for relation in knowledge_base["relations"]:
        if relation["relation"] not in ALLIANCE_RELATIONS:
            continue
        if relation["from"] in participants and relation["to"] not in participants:
            source, target = relation["from"], relation["to"]
        elif relation["to"] in participants and relation["from"] not in participants:
            source, target = relation["to"], relation["from"]
        else:
            continue
        chain.append({
            "from": source,
            "to": target,
            "relation": relation["relation"],
            "reason": relation["reason"],
        })
    return chain


def get_affected_chokepoints(country_a, country_b, severity, duration_days, knowledge_base, escalation_chain=None):
    """Classify routes with an explicit country, commodity, or relationship rationale."""
    conflict_countries = {country_a, country_b}
    chain = escalation_chain or []
    escalated_countries = {item["to"] for item in chain}
    participants = conflict_countries | escalated_countries
    severity_multiplier = knowledge_base["severity_multipliers"][severity]
    duration_multiplier = min(1.0, math.sqrt(duration_days / 90.0))
    origin_basins = {
        basin
        for country in conflict_countries
        for basin in knowledge_base["countries"].get(country, {}).get("primary_export_basins", [])
    }
    affected = []

    for route_id, route in knowledge_base["chokepoints"].items():
        bordering = set(route["bordering_countries"])
        route_commodities = set(route["commodities"])
        direct_links = sorted(conflict_countries & bordering)
        commodity_flows = []
        for country in conflict_countries:
            for commodity in route_commodities:
                commodity_data = knowledge_base["commodities"].get(commodity, {})
                export_key = commodity_data.get("export_share_proxy", commodity)
                country_routes = (
                    knowledge_base.get("country_commodity_routes", {})
                    .get(country, {})
                    .get(export_key, commodity_data.get("chokepoints", []))
                )
                if route_id not in country_routes:
                    continue
                share = get_export_share_pct(country, export_key, knowledge_base)
                if share >= 2.0:
                    commodity_flows.append((country, commodity, share))
        has_country_route_profile = any(
            country in knowledge_base.get("country_commodity_routes", {})
            for country in conflict_countries
        )
        if has_country_route_profile:
            if not direct_links and not commodity_flows:
                continue
        elif (
            not origin_basins.intersection(route["origin_basins"])
            and not commodity_flows
        ):
            continue
        bordering_links = [
            item for item in chain
            if item["to"] in bordering
        ]
        ally_links = [item for item in bordering_links if item["relation"] == "ally"]
        partner_links = [item for item in bordering_links if item["relation"] == "partner"]
        high_export_links = []
        for country in sorted(conflict_countries):
            for commodity in sorted(route_commodities):
                commodity_data = knowledge_base["commodities"].get(commodity, {})
                export_key = commodity_data.get("export_share_proxy", commodity)
                share = get_export_share_pct(country, export_key, knowledge_base)
                if share > DIRECT_EXPORT_THRESHOLD:
                    high_export_links.append((country, commodity, share))

        reasons = []
        impact_type = None
        linked_countries = set()
        if direct_links:
            impact_type = "Direct"
            linked_countries.update(direct_links)
            reasons.extend(
                f"{knowledge_base['countries'].get(country, {}).get('name', country)} borders the {route['name']}."
                for country in direct_links
            )
        elif ally_links or (high_export_links and not partner_links):
            impact_type = "Alliance"
            for link in ally_links:
                linked_countries.update((link["from"], link["to"]))
                reasons.append(
                    f"{knowledge_base['countries'].get(link['from'], {}).get('name', link['from'])} "
                    f"has a {link['relation']} link to "
                    f"{knowledge_base['countries'].get(link['to'], {}).get('name', link['to'])}, "
                    f"which borders the {route['name']}: {link['reason']}"
                )
            for link in partner_links:
                linked_countries.update((link["from"], link["to"]))
                reasons.append(
                    f"{knowledge_base['countries'].get(link['from'], {}).get('name', link['from'])} "
                    f"has a partner link to "
                    f"{knowledge_base['countries'].get(link['to'], {}).get('name', link['to'])}, "
                    f"which borders the {route['name']}: {link['reason']}"
                )
            for country, commodity, share in high_export_links:
                linked_countries.add(country)
                country_name = knowledge_base["countries"].get(country, {}).get("name", country)
                commodity_name = knowledge_base["commodities"].get(commodity, {}).get("name", commodity)
                reasons.append(
                    f"{country_name} supplies {share:.1f}% of global {commodity_name} exports, "
                    f"and {commodity_name} flows through the {route['name']}."
                )
        elif partner_links and not ally_links:
            impact_type = "Spillover"
            for link in partner_links:
                linked_countries.update((link["from"], link["to"]))
                reasons.append(
                    f"{knowledge_base['countries'].get(link['from'], {}).get('name', link['from'])} "
                    f"has a partner link to "
                    f"{knowledge_base['countries'].get(link['to'], {}).get('name', link['to'])}, "
                    f"which borders the {route['name']}: {link['reason']}"
                )
        else:
            for commodity in sorted(route_commodities):
                commodity_data = knowledge_base["commodities"].get(commodity, {})
                export_key = commodity_data.get("export_share_proxy", commodity)
                share = sum(
                    get_export_share_pct(country, export_key, knowledge_base)
                    for country in conflict_countries
                )
                if share > SPILLOVER_THRESHOLD:
                    names = " and ".join(
                        knowledge_base["countries"].get(country, {}).get("name", country)
                        for country in sorted(conflict_countries)
                    )
                    commodity_name = knowledge_base["commodities"].get(commodity, {}).get("name", commodity)
                    reasons.append(
                        f"{names} together account for {share:.1f}% of global {commodity_name} exports, "
                        f"and {commodity_name} is routed through the {route['name']}."
                    )
                    linked_countries.update(
                        country for country in conflict_countries
                        if get_export_share_pct(country, export_key, knowledge_base) >= 2.0
                    )
            if reasons:
                impact_type = "Spillover"

        if not impact_type or not reasons:
            continue

        displayed_commodities = route_commodities
        if has_country_route_profile:
            displayed_commodities = set()
            for country in conflict_countries:
                for commodity in route_commodities:
                    commodity_data = knowledge_base["commodities"].get(commodity, {})
                    export_key = commodity_data.get("export_share_proxy", commodity)
                    country_routes = (
                        knowledge_base.get("country_commodity_routes", {})
                        .get(country, {})
                        .get(export_key, commodity_data.get("chokepoints", []))
                    )
                    if (
                        route_id in country_routes
                        and get_export_share_pct(country, export_key, knowledge_base) >= 2.0
                    ):
                        displayed_commodities.add(commodity)
        elif partner_links and not direct_links and not ally_links:
            partner_countries = {link["to"] for link in partner_links}
            displayed_commodities = {
                commodity
                for commodity in route_commodities
                if any(
                    get_export_share_pct(
                        country,
                        knowledge_base["commodities"].get(commodity, {}).get(
                            "export_share_proxy", commodity
                        ),
                        knowledge_base,
                    ) >= 2.0
                    for country in partner_countries
                )
            }

        base_magnitude = (
            severity_multiplier
            * duration_multiplier
            * (1.0 - route["alternative_route_capacity"])
        )
        if impact_type == "Alliance":
            magnitude = min(0.5, max(0.25, base_magnitude * 0.75))
        elif partner_links and not direct_links and not ally_links:
            magnitude = min(0.15, base_magnitude * 0.5)
        else:
            magnitude = min(1.0, base_magnitude * 0.5)
        affected.append({
            "id": route_id,
            "chokepoint": route["name"],
            "name": route["name"],
            "latitude": route["latitude"],
            "longitude": route["longitude"],
            "bordering_countries": route["bordering_countries"],
            "commodities": sorted(displayed_commodities),
            "annual_trade_value_usd": route["annual_trade_value_usd"],
            "alternative_route_capacity": route["alternative_route_capacity"],
            "impact_type": impact_type,
            "reasoning": " ".join(reasons),
            "description": " ".join(reasons),
            "magnitude": magnitude,
            "linked_countries": sorted(linked_countries),
        })
    return affected
