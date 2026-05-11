# allianz-scraper

Python scraper for Allianz corporate contact country pages that exports both raw office rows and a city-level CSV.

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

Scrape all corporate country pages linked from the Allianz contact index:

```bash
uv run python scripts/allianz_corporate_index_scraper.py --index-url "https://www.allianz.com/en/about-us/company/contact.html"
```

Write to custom output paths:

```bash
uv run python scripts/allianz_corporate_index_scraper.py \
  --index-url "https://www.allianz.com/en/about-us/company/contact.html" \
  --output data/allianz_contact_index_all.csv \
  --city-output data/allianz_contact_index_city.csv
```

## Output

The raw scraper writes a CSV with these columns:

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

Default output files:

- `data/allianz_contact_index_all.csv`
- `data/allianz_contact_index_city.csv`

## Source

The scraper starts from the Allianz corporate contact index and follows the linked country pages:

- `https://www.allianz.com/en/about-us/company/contact.html`

## Project structure

```text
.
├── data/
│   ├── allianz_contact_index_all.csv
│   └── allianz_contact_index_city.csv
├── scripts/
│   └── allianz_corporate_index_scraper.py
├── pyproject.toml
└── uv.lock
```

## Notes

- Uses `cloudscraper` to improve reliability against anti-bot protections.
- Splits multi-office country pages into separate city rows where possible.
- Applies shared page/company phone details to each split office row when the page uses one shared contact block.
- The city-level report header is `country,city,company_type,address,phone`.
