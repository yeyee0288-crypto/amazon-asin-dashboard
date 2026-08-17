# Security Policy

ASIN Watchtower is a local-first tool. It may interact with Amazon pages, local Excel files, and optional private ERP configuration on a user's own machine.

## Supported Versions

The public repository currently supports the latest `main` branch.

## What Not To Share Publicly

Please do not open public issues or pull requests containing:

- ERP accounts, passwords, tokens, cookies, or private URLs.
- Inventory files, exported reports, customer data, or internal SKU lists.
- Debug HTML, screenshots, or logs that include private business data.
- Packaged `.exe` files, local caches, browser profiles, or downloaded ERP files.

## Reporting Security Concerns

If you find a security or sensitive-data issue, please avoid posting secrets in a public GitHub issue.

Use GitHub's private vulnerability reporting if it is available for this repository, or open a minimal public issue that describes the category of risk without including secrets.

## Local Configuration

Use `.env.example` as a template for local settings. Keep real `.env` files, ERP credentials, cookies, and runtime caches on your own machine.

The repository `.gitignore` is configured to exclude common business files and runtime data, but contributors should still review changes before committing.
