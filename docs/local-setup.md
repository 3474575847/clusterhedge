# ClusterHedge — Local Setup Guide

This guide downloads and runs the ClusterHedge Flask app on your own computer.
It does not deploy a shared or public instance.

## Requirements

- Python 3.11 or newer
- Git (optional, if you clone rather than download the ZIP)
- Internet access to install Python dependencies; some application features
  also request external data

Installing `geopandas` and its native dependencies can require platform-specific
setup. If dependency installation fails, consult the relevant package
documentation for your operating system.

## Get the source

Choose one:

- [Download the ZIP archive](https://github.com/3474575847/clusterhedge/archive/refs/heads/main.zip),
  extract it, and open a terminal in the extracted `clusterhedge-main` folder.
- Or clone with Git:

  ```bash
  git clone https://github.com/3474575847/clusterhedge.git
  cd clusterhedge
  ```

## Create an environment and install dependencies

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The example `.env` contains only a placeholder development setting. Current
market-data and geographic lookup features use `yfinance` and the OpenStreetMap
Overpass API; they do not currently require you to supply API keys. Availability
and terms of those external services can change.

## Start the application

With the virtual environment active:

```bash
python app.py
```

Open <http://127.0.0.1:5011> in your browser. Stop the local server with
`Ctrl+C`.

The app starts with an empty local database. To add the optional Seattle sample
project and materials, run `python seed.py` once from the project directory.
The script does not run automatically, and each additional run inserts another
copy of the sample records.

## Run tests

```bash
python -m unittest discover -s tests
```

## Refresh bundled geopolitical data (optional)

The repository includes dated FAOSTAT export snapshots and FRED benchmark-price
history. The geopolitical simulation reads these files locally and does not
download them on every run. If you intentionally want to refresh the bundled
data, use the system `curl` utility and run:

```bash
python scripts/refresh_geopolitical_sources.py --year 2024
```

This fetches FRED price series and the large FAOSTAT bulk archive; no API key is
currently required. Use `--prices-only` or `--exports-only` to refresh just one
snapshot. To reuse a previously downloaded FAOSTAT archive, add
`--faostat-archive PATH`. Review the generated metadata and resulting diffs
before sharing refreshed snapshots.

The simulation uses FAOSTAT country export-value shares for wheat, corn, and
rice where available. It estimates annualized volatility from recent FRED
benchmark returns where available; other values remain explicitly labeled
illustrative assumptions. Correlation groups, commodity elasticities,
substitution, reserve coverage, route capacities, and relationship data are
not comprehensively verified current market data. Shock intervals are based on
1,000 correlated lognormal samples, not guarantees or forecasts.

## Data and safety

- The app uses a local SQLite database by default. Do not commit or share your
  database file if it contains information you do not want public.
- The app has no login or per-user access controls. Keep it local; do not
  expose it to the internet with private data.
- Outputs are experimental estimates, not investment, trading, engineering, or
  legal advice. Do not rely on them to make financial decisions.
- The web interface loads some assets from third-party CDNs. Data-provider
  availability, accuracy, and terms are outside the project's control.

For project background and limitations, see the
[README](https://github.com/3474575847/clusterhedge#readme).
