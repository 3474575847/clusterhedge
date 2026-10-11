#!/usr/bin/env python3
"""Refresh versioned public price and crop-trade snapshots used by the simulation."""

import argparse
import csv
import io
import json
import subprocess
import tempfile
import time
import zipfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KB_PATH = ROOT / "engine" / "knowledge_base.json"
SNAPSHOT_DIR = ROOT / "engine" / "data_snapshots"
FAOSTAT_URL = (
    "https://bulks-faostat.fao.org/production/"
    "Trade_CropsLivestock_E_All_Data_(Normalized).zip"
)
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
PRICE_SERIES = {
    "wheat": ("PWHEAMTUSDM", "monthly"),
    "corn": ("PMAIZMTUSDM", "monthly"),
    "rice": ("PRICENPQUSDM", "monthly"),
    "crude_oil": ("DCOILBRENTEU", "daily"),
    "copper": ("PCOPPUSDM", "monthly"),
}
FAOSTAT_ITEMS = {
    "wheat": "Wheat",
    "corn": "Maize (corn)",
    "rice": "Rice, paddy (rice milled equivalent)",
}
AREA_ALIASES = {
    "Russian Federation": "russia",
    "United States of America": "united_states",
    "Viet Nam": "vietnam",
    "Türkiye": "turkey",
    "Iran (Islamic Republic of)": "iran",
    "Bolivia (Plurinational State of)": "bolivia",
    "Venezuela (Bolivarian Republic of)": "venezuela",
}


def download(url):
    return subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "120", url],
        check=True,
        capture_output=True,
    ).stdout


def download_to_file(url, path):
    with path.open("wb") as archive_file:
        subprocess.run(
            [
                "curl", "--fail", "--silent", "--show-error", "--location",
                "--max-time", "300", url,
            ],
            check=True,
            stdout=archive_file,
        )


def refresh_prices():
    rows = []
    failures = []
    for commodity_id, (series_id, frequency) in PRICE_SERIES.items():
        url = f"{FRED_URL}?id={series_id}&cosd=2015-01-01"
        try:
            content = download(url).decode("utf-8-sig")
        except Exception as error:
            failures.append(f"{series_id}: {error}")
            continue
        reader = csv.DictReader(io.StringIO(content))
        value_column = next(
            (name for name in (reader.fieldnames or []) if name != "observation_date"),
            None,
        )
        if not value_column:
            failures.append(f"{series_id}: FRED response did not include an observation column")
            continue
        series_rows = 0
        for observation in reader:
            value = observation.get(value_column, "").strip()
            if not value or value == ".":
                continue
            rows.append({
                "commodity_id": commodity_id,
                "series_id": series_id,
                "date": observation["observation_date"],
                "value": value,
                "frequency": frequency,
                "source": "FRED graph CSV; series underlying sources documented in metadata",
            })
            series_rows += 1
        if not series_rows:
            failures.append(f"{series_id}: no usable observations returned")
        time.sleep(0.25)

    if not rows:
        raise RuntimeError("No price series were refreshed; existing snapshots were not changed.")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / "fred_prices.csv"
    with path.open("w", encoding="utf-8", newline="") as snapshot_file:
        writer = csv.DictWriter(
            snapshot_file,
            fieldnames=rows[0].keys(),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    metadata_path = SNAPSHOT_DIR / "fred_prices.metadata.json"
    metadata = {
        "source": "Federal Reserve Bank of St. Louis FRED graph CSV endpoint",
        "source_url": FRED_URL,
        "accessed_on": date.today().isoformat(),
        "snapshot": path.name,
        "series": {
            commodity_id: {
                "series_id": series_id,
                "frequency": frequency,
                "series_url": f"https://fred.stlouisfed.org/series/{series_id}",
            }
            for commodity_id, (series_id, frequency) in PRICE_SERIES.items()
            if any(row["commodity_id"] == commodity_id for row in rows)
        },
        "coverage_start": min(row["date"] for row in rows),
        "coverage_end": max(row["date"] for row in rows),
        "limitations": [
            "Series are benchmark proxies, not local transaction prices.",
            "FRED series coverage and units differ by commodity; validate before operational use.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(path.relative_to(ROOT)),
        "metadata": str(metadata_path.relative_to(ROOT)),
        "rows": len(rows),
        "failures": failures,
    }


def _country_ids():
    with KB_PATH.open(encoding="utf-8") as knowledge_file:
        knowledge_base = json.load(knowledge_file)
    country_ids = {}
    for country_id, country in knowledge_base["countries"].items():
        country_ids[country["name"]] = country_id
    country_ids.update(AREA_ALIASES)
    return country_ids


def refresh_faostat_exports(year, archive_path=None):
    if archive_path:
        archive = Path(archive_path)
        archive_context = None
    else:
        archive_context = tempfile.TemporaryDirectory(prefix="clusterhedge-faostat-")
        archive = Path(archive_context.name) / "faostat.zip"
        download_to_file(FAOSTAT_URL, archive)

    country_ids = _country_ids()
    records = {
        commodity_id: {"item": item, "world": None, "countries": {}}
        for commodity_id, item in FAOSTAT_ITEMS.items()
    }
    try:
        with zipfile.ZipFile(archive) as data_zip:
            csv_name = next(
                (name for name in data_zip.namelist() if name.endswith(".csv") and "All_Data" in name),
                None,
            )
            if not csv_name:
                raise RuntimeError("FAOSTAT archive did not contain the normalized trade CSV.")
            with data_zip.open(csv_name) as data_file:
                text_stream = io.TextIOWrapper(data_file, encoding="utf-8-sig", newline="")
                for row in csv.DictReader(text_stream):
                    if row["Year"] != str(year) or row["Element"] not in {"Export value", "Import value"}:
                        continue
                    commodity_id = next(
                        (
                            commodity for commodity, item in FAOSTAT_ITEMS.items()
                            if row["Item"] == item
                        ),
                        None,
                    )
                    if not commodity_id:
                        continue
                    try:
                        value = float(row["Value"])
                    except (TypeError, ValueError):
                        continue
                    area = row["Area"]
                    country_id = country_ids.get(area)
                    target = records[commodity_id]
                    if area == "World" and row["Element"] == "Export value":
                        target["world"] = value
                    elif country_id:
                        record = target["countries"].setdefault(country_id, {
                            "export_value_1000_usd": None,
                            "import_value_1000_usd": None,
                            "export_flag": None,
                            "import_flag": None,
                        })
                        if row["Element"] == "Export value":
                            record["export_value_1000_usd"] = value
                            record["export_flag"] = row["Flag"]
                        else:
                            record["import_value_1000_usd"] = value
                            record["import_flag"] = row["Flag"]
    finally:
        if archive_context:
            archive_context.cleanup()

    snapshot = {
        "metadata": {
            "source": "FAOSTAT Trade: Crops and livestock products (normalized)",
            "dataset_url": "https://www.fao.org/faostat/en/#data/TCL",
            "bulk_url": FAOSTAT_URL,
            "reference_year": year,
            "accessed_on": date.today().isoformat(),
            "measure": "Export value in thousands of current US dollars; share is country export value divided by FAOSTAT World export value.",
            "net_importer_rule": "True when reported import value exceeds reported export value for the same FAOSTAT item and reference year.",
            "flags_note": "FAOSTAT country flags are preserved; X/E indicate estimates and are not equivalent to unflagged reported observations.",
        },
        "commodities": {},
    }
    for commodity_id, source_data in records.items():
        world_value = source_data["world"]
        if not world_value or world_value <= 0:
            raise RuntimeError(
                f"FAOSTAT supplied no World export-value denominator for {source_data['item']} in {year}."
            )
        countries = {}
        for country_id, values in source_data["countries"].items():
            export_value = values["export_value_1000_usd"]
            if export_value is None:
                continue
            import_value = values["import_value_1000_usd"]
            countries[country_id] = {
                **values,
                "export_share_pct": export_value / world_value * 100.0,
                "net_importer": (
                    import_value > export_value if import_value is not None else None
                ),
                "net_importer_status": (
                    "determined" if import_value is not None else "unavailable"
                ),
            }
        snapshot["commodities"][commodity_id] = {
            "source_item": source_data["item"],
            "world_export_value_1000_usd": world_value,
            "countries": countries,
        }

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / "faostat_exports.json"
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return {"path": str(path.relative_to(ROOT)), "commodities": len(snapshot["commodities"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024, help="FAOSTAT reference year")
    parser.add_argument("--faostat-archive", help="Use a previously downloaded FAOSTAT ZIP")
    parser.add_argument("--prices-only", action="store_true")
    parser.add_argument("--exports-only", action="store_true")
    args = parser.parse_args()

    if not args.exports_only:
        print("Prices:", refresh_prices())
    if not args.prices_only:
        print("FAOSTAT exports:", refresh_faostat_exports(args.year, args.faostat_archive))
    print("UN Comtrade, USGS, UNCTAD, Drewry, Lloyd's List, COW, and ATOP availability is documented separately; this command does not imply coverage of unavailable/licensed series.")


if __name__ == "__main__":
    main()
