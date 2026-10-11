# Privacy Notice — unfinished draft

**Status: incomplete. Do not treat this as a final or legally reviewed privacy
policy.** The maintainer's public contact address, operator identity, retention
period, and deployment-specific practices have not been supplied. Complete
these items and obtain appropriate legal review before making a hosted service
available to the public.

**Last updated:** 2026-10-11

## Scope

This notice describes data flows visible in the ClusterHedge source code. It
does not describe every practice of a person or company that deploys a copy of
the software. A self-hosting operator is responsible for documenting their own
hosting, logging, retention, and data-subject request procedures.

## Data the application can handle

The application has no user accounts. Visitors can enter project names and
descriptions, material names, quantities, estimated costs, market views, and
optional location names and coordinates. These records are stored in the
configured SQLAlchemy database. By default, local development uses SQLite.
There is no per-user separation: on a shared public deployment, visitors may
be able to see or alter other visitors' project records.

The application does not currently provide an account-based export or deletion
workflow. Database retention and deletion depend on the operator and hosting
configuration.

## Third-party requests and browser resources

- Market-data features use `yfinance` to request historical market information
  from Yahoo Finance. Ticker symbols and request metadata may be visible to
  Yahoo Finance and relevant network providers.
- The location agglomeration feature sends coordinates and an Overpass query
  to the OpenStreetMap Overpass API (`overpass-api.de`).
- The user interface loads resources from the Tailwind CSS CDN, unpkg, and
  Google Fonts. Those services may receive ordinary browser request metadata,
  such as IP address and user-agent.

These services have their own terms and privacy practices; review the current
notices from each provider before relying on them.

## Hosting and logs

If the application is hosted, the hosting provider may process connection
logs, deployment metadata, and other information under its own terms. The
operator must add the actual provider, logging, database, backup, and retention
details here before launch.

## Contact and applicable requirements — incomplete

- **Operator/data controller:** TODO
- **Public privacy contact:** TODO — provide a monitored address that is safe
  to publish.
- **Retention and deletion periods:** TODO
- **Applicable jurisdiction and privacy-rights process:** TODO — operator is
  based in India; obtain advice on applicable Indian and other laws before
  launch.

Do not submit personal, confidential, or sensitive information to a public
demo. Do not send private data-protection requests or security reports through
public GitHub issues.
