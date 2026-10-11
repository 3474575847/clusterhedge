# ClusterHedge

ClusterHedge is an experimental Flask application for exploring material cost
exposure, proxy-ETF relationships, scenario analysis, and supply-chain risks.
It includes project/material tracking, Monte Carlo simulations, hedge
recommendations, backtesting, sustainability estimates, and a geopolitical
scenario view.

This is a research/learning prototype, not production-ready financial software.
Its estimates can be incomplete or wrong and are not investment, trading,
engineering, or legal advice. Do not use it to make financial decisions or
enter confidential or sensitive information.

## Status and important limitations

- The app has no user accounts, authentication, or per-user access controls.
  Anyone who can reach a deployed instance can potentially view or change its
  projects. Do not expose an instance containing non-public data to the
  internet.
- Local development uses SQLite. Serverless filesystems may be temporary, so
  local SQLite is not durable storage for a serverless deployment.
- Some features request market history through `yfinance`/Yahoo Finance and
  geographic data from the OpenStreetMap Overpass API. Results, availability,
  and terms are controlled by those third parties.
- The UI loads Tailwind CSS, vis-network, and fonts from external CDNs.
- This repository does not include a production deployment configuration.

## Run locally

Python 3.11 or newer is recommended. Native geospatial dependencies may require
platform-specific setup.

```bash
git clone https://github.com/3474575847/clusterhedge.git
cd clusterhedge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open <http://127.0.0.1:5000>. On Windows, activate the environment with
`.venv\Scripts\activate` instead of the `source` command.

The generated `.env` is for local development only. Set a private `SECRET_KEY`
in the environment of any deployment. Never commit `.env` files, database
files, or credentials.

## Tests

```bash
python -m unittest discover -s tests
```

## Deployment

Vercel currently documents support for Flask, but this app is not ready to be
deployed publicly as-is: it has no authentication, runs schema checks during
requests, and defaults to local SQLite. Before deploying for real use, add
access controls, choose persistent storage, review third-party data handling,
and test the full dependency bundle and request duration on the selected host.
See the official [Vercel Flask guide](https://vercel.com/docs/frameworks/backend/flask)
and [function limits](https://vercel.com/docs/functions/limitations). A free
plan is subject to the provider's current eligibility, usage limits, and terms;
check those directly before deploying.

## Project and legal notices

- [Privacy notice (unfinished draft)](PRIVACY.md)
- [Terms and financial disclaimer (unfinished draft)](TERMS.md)
- [Security reporting](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [MIT License](LICENSE)

The privacy and terms documents are incomplete templates, not legal advice or
assurance of compliance. Complete and have them reviewed before operating a
public service.
