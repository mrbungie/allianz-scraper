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

Write both the full report and the city-level report to custom paths:

```bash
uv run python scripts/allianz_scraper.py --output data/allianz_offices.csv --city-output data/allianz_city_offices.csv
```

If you already have `data/allianz_offices.csv` and only want to rebuild the processed city-level file:

```bash
uv run python scripts/allianz_city_report.py --input data/allianz_offices.csv --output data/allianz_city_offices.csv
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

It also writes a second city-level CSV with one selected record per country/city and these columns:

- `country`
- `city`
- `company_type`
- `address`
- `phone`

Default output file:

- `data/allianz_offices.csv`
- `data/allianz_city_offices.csv`

## Sources

The script aggregates data from:

- Allianz corporate contact pages
- Allianz Commercial global office pages
- Allianz Technology contact pages

## Project structure

```text
.
├── data/
│   ├── allianz_city_offices.csv
│   └── allianz_offices.csv
├── scripts/
│   ├── allianz_city_report.py
│   └── allianz_scraper.py
├── pyproject.toml
└── uv.lock
```

## Notes

- Uses `cloudscraper` to improve reliability against anti-bot protections.
- De-duplicates records by business unit, country, office name, and address.
- The city-level report keeps one best-fit record per country/city, preferring head-office style entries over generic contacts.
- The checked-in CSV is a generated dataset sample/output.
