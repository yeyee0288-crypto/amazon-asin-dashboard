# ASIN Watchtower

**Amazon ASIN price, availability, seller, and inventory risk monitor for marketplace operators.**

ASIN Watchtower is a local web dashboard for marketplace teams that need to monitor many Amazon ASINs at once. It helps operators spot price changes, out-of-stock redirects, seller changes, low-stock warnings, ERP inventory risk, and differences from the previous run.

It is designed for people who manage Amazon listings, store links, ERP SKUs, and replenishment decisions every day.

## Why This Exists

Marketplace operators often need to answer questions like:

- Which ASINs changed price since the last check?
- Which products are sellable on Amazon but have no ERP stock?
- Which ASINs are out of stock on Amazon while ERP still has inventory?
- Which listings redirected to another ASIN and should be treated as unavailable?
- Which seller, brand, ERP SKU, or store-link group needs attention first?

ASIN Watchtower turns those checks into a local workflow that can be reviewed, filtered, compared, and exported.

## Features

- Batch input of Amazon ASINs or product links.
- Grouping by store link name and ERP SKU.
- Amazon status detection, including missing offer, out-of-stock, low-stock hints, and ASIN redirect mismatch.
- Optional ERP inventory import and SKU mapping import from Excel files.
- Optional local ERP auto-update via environment variables.
- Excel export for current results.
- Local history comparison for the previous run.

## Product Positioning

**For Amazon operators and marketplace teams**, ASIN Watchtower is a local monitoring workspace that combines Amazon listing checks with ERP inventory context, so teams can catch sellability, replenishment, and pricing risks before they become operational problems.

Unlike one-off scraping scripts, it provides a dashboard, filters, local history comparison, Excel export, and inventory-risk classification in one workflow.

## Privacy And Data

This repository is source-code only. Do not commit operational data.

Ignored local data includes:

- ERP inventory files: `.xlsx`, `.xls`, `.csv`
- Runtime caches: `erp_inventory_cache.json`, `sku_map_cache.json`, `last_results_cache.json`, `erp_auto_config.json`
- ERP downloads and debug files
- Build outputs: `build/`, `dist/`, `.exe`, `.zip`
- Python caches and virtual environments

ERP URLs, accounts, passwords, tokens, cookies, and inventory data should stay on each user's machine.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py --port 8080
```

Then open:

```text
http://127.0.0.1:8080
```

## Optional ERP Configuration

Copy `.env.example` to `.env` for local-only settings.

```powershell
Copy-Item .env.example .env
```

Fill in your own ERP URLs and credentials in the dashboard or local environment. Never commit `.env`.

## Roadmap

- Cleaner public demo dataset with fake ASIN/SKU examples.
- Optional chat alert integrations.
- Scheduled monitoring runs.
- Better anti-redirect evidence and screenshots for unavailable ASINs.
- Docker packaging for server deployment.

## Build Windows App

```powershell
python -m PyInstaller --clean -y AmazonASINDashboard.spec
```

The build output will be generated under `dist/`.

## GitHub Safety Checklist

Before publishing:

```powershell
git status --short --ignored
git ls-files
```

Only source files, templates, static assets, docs, and sample config should be tracked.
