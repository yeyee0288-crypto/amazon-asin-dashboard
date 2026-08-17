# Amazon ASIN Dashboard

A local web dashboard for batch checking Amazon ASIN price, availability, seller, brand, ERP SKU inventory risk, and result changes.

## Features

- Batch input of Amazon ASINs or product links.
- Grouping by store link name and ERP SKU.
- Amazon status detection, including missing offer, out-of-stock, low-stock hints, and ASIN redirect mismatch.
- Optional ERP inventory import and SKU mapping import from Excel files.
- Optional local ERP auto-update via environment variables.
- Excel export for current results.
- Local history comparison for the previous run.

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
