"""Load reproducible source snapshots without network access at app runtime."""

import csv
from functools import lru_cache
import json
import math
from pathlib import Path


SNAPSHOT_DIR = Path(__file__).with_name("data_snapshots")
EXPORT_SNAPSHOT_PATH = SNAPSHOT_DIR / "faostat_exports.json"
PRICE_SNAPSHOT_PATH = SNAPSHOT_DIR / "fred_prices.csv"


@lru_cache(maxsize=1)
def _load_export_snapshot():
    if not EXPORT_SNAPSHOT_PATH.exists():
        return None
    with EXPORT_SNAPSHOT_PATH.open(encoding="utf-8") as snapshot_file:
        return json.load(snapshot_file)


def load_export_record(country_id, commodity_id):
    """Return a source-backed FAOSTAT export record when the snapshot has one."""
    snapshot = _load_export_snapshot()
    if snapshot is None:
        return None
    return (
        snapshot.get("commodities", {})
        .get(commodity_id, {})
        .get("countries", {})
        .get(country_id)
    )


def load_export_snapshot_metadata():
    """Return the provenance for the dated FAOSTAT export snapshot, if present."""
    snapshot = _load_export_snapshot()
    return snapshot.get("metadata") if snapshot else None


def get_export_share_pct(country_id, commodity_id, knowledge_base):
    """Prefer the dated FAOSTAT share; otherwise return its labeled KB fallback."""
    record = load_export_record(country_id, commodity_id)
    if record is not None:
        if record.get("net_importer") is True:
            return 0.0
        return record["export_share_pct"]
    if commodity_id in knowledge_base["countries"].get(country_id, {}).get(
        "net_importers", []
    ):
        return 0.0
    return (
        knowledge_base["countries"]
        .get(country_id, {})
        .get("exports", {})
        .get(commodity_id, 0.0)
    )


@lru_cache(maxsize=None)
def calculate_realized_volatility(commodity_id):
    """Calculate annualized realized volatility from the latest 30 source returns."""
    if not PRICE_SNAPSHOT_PATH.exists():
        return None

    observations = []
    with PRICE_SNAPSHOT_PATH.open(encoding="utf-8", newline="") as snapshot_file:
        for row in csv.DictReader(snapshot_file):
            if row["commodity_id"] != commodity_id:
                continue
            try:
                value = float(row["value"])
            except (TypeError, ValueError):
                continue
            if value > 0:
                observations.append((
                    row["date"], value, row["frequency"], row["series_id"]
                ))

    observations.sort(key=lambda row: row[0])
    if len(observations) < 3:
        return None

    frequency = observations[-1][2]
    return_window = observations[-31:]
    returns = [
        math.log(current[1] / previous[1])
        for previous, current in zip(return_window, return_window[1:])
    ]
    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
    periods_per_year = 252 if frequency == "daily" else 12
    return {
        "annualized_volatility": math.sqrt(variance * periods_per_year),
        "frequency": frequency,
        "observations": len(return_window),
        "start_date": return_window[0][0],
        "end_date": return_window[-1][0],
        "series_id": next(
            row[3]
            for row in reversed(observations)
            if row[2] == frequency
        ),
        "source": "FRED graph CSV snapshot",
    }
