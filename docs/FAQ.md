# FAQ

## Does ASIN Watchtower upload my data?

No. The project is designed as a local-first dashboard. ASIN lists, ERP files, runtime cache, and exported results stay on your own machine unless you choose to share them.

## Why does it run locally instead of as a hosted SaaS?

Marketplace teams often handle private ASIN batches, ERP SKUs, inventory files, and internal workflows. Running locally keeps those files out of a public server by default.

## Do I need ERP integration to use it?

No. ERP inventory is optional. You can use ASIN Watchtower only for Amazon price, availability, redirect, seller, and previous-run comparison.

## What input format does it support?

You can paste ASINs or Amazon product links directly into the dashboard. For spreadsheet import, use columns similar to:

| ASIN or URL | Store-link name | ERP SKU | Expected price |
| --- | --- | --- | --- |
| `B000000001` | `Demo-Store-A` | `T-DEMO-001-BK` | `99.99` |

See [`../examples/sample-asins.csv`](../examples/sample-asins.csv).

## Why does Chrome or ChromeDriver matter?

The scraper uses browser automation for pages that are difficult to parse with plain HTTP requests. Chrome and ChromeDriver version mismatches can cause startup failures. If that happens, update Chrome and the matching driver setup before running a new batch.

## Can it detect every out-of-stock case perfectly?

No scraper can guarantee perfect detection on dynamic marketplace pages. ASIN Watchtower focuses on practical signals such as missing usable price, missing offer, redirect mismatch, low-stock hints, and comparison against previous results.

For public bug reports, use fake or minimal public-safe examples.

## Can I package it as a Windows app?

Yes. The repository includes PyInstaller configuration for building a local Windows app. Build outputs are intentionally ignored by Git because `.exe` files should not be committed to the source repository.

## Can this monitor other marketplaces?

The current implementation focuses on Amazon. The roadmap includes pluggable marketplace adapters, but each marketplace needs its own page rules, status logic, and compliance review.

## Is this affiliated with Amazon?

No. ASIN Watchtower is an independent open-source project for local operational monitoring workflows.

## What should I never commit?

Do not commit ERP accounts, passwords, tokens, cookies, real inventory files, private ASIN batches, exported reports, debug HTML, screenshots with private data, `.env` files, or packaged binaries.
