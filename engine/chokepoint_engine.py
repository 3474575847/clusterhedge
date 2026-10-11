"""Data-driven route exposure classification."""

import math


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
    affected = []

    for route_id, route in knowledge_base["chokepoints"].items():
        bordering = set(route["bordering_countries"])
        route_commodities = set(route["commodities"])
        direct_links = sorted(conflict_countries & bordering)
        alliance_links = [
            item for item in chain
            if item["to"] in bordering
        ]
        high_export_links = []
        for country in sorted(conflict_countries):
            country_data = knowledge_base["countries"].get(country, {})
            for commodity in sorted(route_commodities):
                share = country_data.get("exports", {}).get(commodity, 0)
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
        elif alliance_links or high_export_links:
            impact_type = "Alliance"
            for link in alliance_links:
                linked_countries.update((link["from"], link["to"]))
                reasons.append(
                    f"{knowledge_base['countries'].get(link['from'], {}).get('name', link['from'])} "
                    f"has a {link['relation']} link to "
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
        else:
            for commodity in sorted(route_commodities):
                share = sum(
                    knowledge_base["countries"].get(country, {}).get("exports", {}).get(commodity, 0)
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
                        if knowledge_base["countries"].get(country, {}).get("exports", {}).get(commodity, 0) >= 2.0
                    )
            if reasons:
                impact_type = "Spillover"

        if not impact_type or not reasons:
            continue

        category_factor = {"Direct": 1.0, "Alliance": 0.75, "Spillover": 0.5}[impact_type]
        magnitude = min(
            1.0,
            severity_multiplier * duration_multiplier
            * (1.0 - route["alternative_route_capacity"]) * category_factor,
        )
        affected.append({
            "id": route_id,
            "chokepoint": route["name"],
            "name": route["name"],
            "latitude": route["latitude"],
            "longitude": route["longitude"],
            "bordering_countries": route["bordering_countries"],
            "commodities": sorted(route_commodities),
            "annual_trade_value_usd": route["annual_trade_value_usd"],
            "alternative_route_capacity": route["alternative_route_capacity"],
            "impact_type": impact_type,
            "reasoning": " ".join(reasons),
            "description": " ".join(reasons),
            "magnitude": magnitude,
            "linked_countries": sorted(linked_countries),
        })
    return affected
