"""Apply commodity shocks to blueprint and project bill-of-material items."""

import re


MATERIAL_COMMODITIES = {
    "wheat": "wheat", "grain": "wheat", "rice": "rice", "corn": "corn",
    "fertilizer": "fertilizer", "oil": "crude_oil", "energy": "crude_oil",
    "lpg": "lpg", "steel": "steel", "lumber": "lumber", "wood": "lumber",
    "copper": "copper", "transport": "transport", "freight": "transport",
}


def _commodity_for_material(name):
    lowered = name.casefold()
    for word, commodity in MATERIAL_COMMODITIES.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            return commodity
    return None


def _blueprint_items(project, knowledge_base):
    project_name = getattr(project, "name", str(project))
    known = knowledge_base["boms"].get(project_name.casefold())
    if known:
        return known["items"]

    items = []
    for material in getattr(project, "materials", []):
        commodity = _commodity_for_material(material.name)
        if not commodity:
            continue
        items.append({
            "name": material.name,
            "commodity": commodity,
            "quantity": material.quantity or 0,
            "base_cost": material.estimated_cost or 0,
        })
    return items


def calculate_bom_impact(project, price_shocks, knowledge_base):
    """Return a line-item breakdown and total impact in the project's base currency."""
    breakdown = []
    for item in _blueprint_items(project, knowledge_base):
        shock = price_shocks.get(item["commodity"])
        base_cost = float(item["base_cost"]) * float(item.get("quantity", 1))
        expected_shock = shock["expected"] if shock else 0.0
        delta_cost = base_cost * expected_shock
        breakdown.append({
            "name": item["name"],
            "commodity": knowledge_base["commodities"][item["commodity"]]["name"],
            "commodity_id": item["commodity"],
            "quantity": item.get("quantity", 1),
            "shock_pct": expected_shock,
            "base_cost": base_cost,
            "delta_cost": delta_cost,
            "ci_low": shock["ci_low"] if shock else 0.0,
            "ci_high": shock["ci_high"] if shock else 0.0,
        })
    return {
        "items": breakdown,
        "total_base_cost": sum(item["base_cost"] for item in breakdown),
        "total_delta_cost": sum(item["delta_cost"] for item in breakdown),
    }
