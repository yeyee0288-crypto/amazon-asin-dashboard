# Roadmap

ASIN Watchtower focuses on one practical job: helping marketplace operators quickly see which Amazon ASINs changed price, became unavailable, redirected to another ASIN, or need inventory attention.

## Now

- Local dashboard for batch ASIN and Amazon link checks.
- Expected price vs current price comparison.
- Availability, missing offer, low-stock hint, and redirect mismatch detection.
- Seller, brand, title, store-link name, and ERP SKU display.
- Previous-run comparison and Excel export.
- Optional ERP inventory import and SKU mapping from local files.

## Near Term

- Public-safe demo mode with fake rows already loaded.
- Clearer failed-check retry workflow.
- More transparent status evidence for price and availability results.
- Better Windows packaging notes for non-technical users.
- More sample input templates for common marketplace workflows.

## Later

- Scheduled local monitoring runs.
- Optional notification integrations for urgent price or stock changes.
- Docker-based deployment for teams that want a shared internal instance.
- Pluggable marketplace adapters beyond Amazon.
- Test fixtures for status detection logic using sanitized HTML snapshots.

## Product Principles

- Keep sensitive business data local by default.
- Make status decisions explainable to operators.
- Prefer useful workflow clarity over noisy dashboards.
- Treat price changes and availability changes as first-class signals.
- Make exports easy for follow-up, audits, and team handoff.
