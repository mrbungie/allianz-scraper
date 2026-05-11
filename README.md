# allianz-scraper

Python scraper that collects Allianz office/contact data from Allianz corporate, commercial, and technology pages and exports it to CSV.

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) recommended for dependency management

## Install

```bash
uv sync
```

If you prefer pip:

```bash
pip install beautifulsoup4 cloudscraper requests
```

## Usage

Write to the default output path:

```bash
uv run python scripts/allianz_scraper.py
```

Write to a custom CSV path:

```bash
uv run python scripts/allianz_scraper.py --output data/allianz_offices.csv
```

## Output

The scraper writes a CSV with these columns:

- `business_unit`
- `country`
- `office_name`
- `office_type`
- `city`
- `address`
- `postcode`
- `phone`
- `email`
- `website`
- `source_url`
- `source_page`
- `notes`

Default output file:

- `data/allianz_offices.csv`

## Sources

The script aggregates data from:

- Allianz corporate contact pages
- Allianz Commercial global office pages
- Allianz Technology contact pages

## Project structure

```text
.
├── data/
│   └── allianz_offices.csv
├── scripts/
│   └── allianz_scraper.py
├── pyproject.toml
└── uv.lock
```

## Notes

- Uses `cloudscraper` to improve reliability against anti-bot protections.
- De-duplicates records by business unit, country, office name, and address.
- The checked-in CSV is a generated dataset sample/output.
