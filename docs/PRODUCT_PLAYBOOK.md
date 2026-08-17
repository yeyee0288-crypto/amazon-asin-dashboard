# ASIN Watchtower Product Playbook

## Target Users

- Amazon marketplace operators who manage many ASINs.
- E-commerce teams that use ERP SKUs and need inventory-risk visibility.
- Small teams that want a local tool before investing in a full SaaS system.

## Core Message

ASIN Watchtower helps Amazon operators detect listing, price, seller, redirect, and ERP inventory risks before they become operational problems.

## GitHub Positioning

Use this one-line description:

```text
Open-source Amazon ASIN price, availability, seller, redirect, and ERP inventory risk monitor for marketplace operators.
```

Suggested topics:

```text
amazon, asin, inventory, ecommerce, marketplace, price-monitoring, selenium, flask, erp, operations-dashboard
```

## Star Growth Plan

1. Add a clean screenshot or demo GIF to the README.
2. Publish a short LinkedIn/X post explaining the operator pain point.
3. Share in ecommerce, Amazon seller, and operations communities.
4. Add a fake demo dataset so people can test without private data.
5. Open 3-5 beginner-friendly GitHub issues to invite contributors.
6. Create release notes for each meaningful improvement.

## Public Demo Dataset

Do not use real company ASINs, ERP SKUs, seller names, or inventory.

Create fake examples like:

- ASIN: `B000000001`
- Store link name: `Demo-Store-HAD25`
- ERP SKU: `DEMO-HAD25-100BK`
- Expected price: `$99.99`

## Roadmap Themes

- Reliability: fewer false out-of-stock results, better retry strategy.
- Evidence: capture redirect evidence and page ASIN proof.
- Automation: scheduled runs and notification integrations.
- Usability: import templates, sample data, and onboarding.
- Distribution: Docker image, Windows release, and hosted demo.

## Release Rhythm

- Patch releases: bug fixes and scraping stability.
- Minor releases: dashboard, import, export, or alert improvements.
- Major releases: architecture changes, hosted mode, or multi-market support.

## What Not To Publish

- ERP credentials, URLs, cookies, tokens, downloaded inventory, or debug HTML.
- Real company ASIN lists, ERP SKUs, store names, seller lists, or internal department names.
- Packaged `.exe` files in the main source repository unless attached to GitHub Releases.
