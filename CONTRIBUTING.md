# Contributing

Thanks for helping improve ASIN Watchtower.

This project is built for marketplace operators who need a practical local tool for checking Amazon ASIN price and availability signals.

## Good Contributions

- More reliable price and offer detection.
- Better ASIN redirect and unavailable-listing handling.
- Cleaner dashboard filters and result review flows.
- Safer local inventory import and matching logic.
- Documentation, examples, and packaging improvements.

## Before Opening A Pull Request

1. Keep changes focused.
2. Use fake data in examples and screenshots.
3. Do not commit `.xlsx`, `.csv`, `.env`, cache files, cookies, debug HTML, screenshots with private data, or build outputs.
4. Run the app locally if your change touches the dashboard or scraper.
5. Explain the user-facing impact in the pull request description.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py --port 8080
```

Open `http://127.0.0.1:8080`.

## Privacy Rules

Never include:

- ERP accounts, passwords, tokens, cookies, or internal URLs.
- Real inventory files or exported business reports.
- Private ASIN batches tied to business operations.
- Local debug files that may contain page HTML or screenshots.

If you need to demonstrate a bug, reduce it to the smallest public-safe example.
