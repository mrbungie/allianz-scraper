from __future__ import annotations

import argparse
from pathlib import Path

from allianz_scraper import CORPORATE_INDEX, AllianzScraper, build_city_report, write_city_report, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Allianz corporate country pages from the contact index")
    parser.add_argument(
        "--index-url",
        default=CORPORATE_INDEX,
        help="Corporate contact index page to crawl for country pages",
    )
    parser.add_argument(
        "--output",
        default="data/allianz_contact_index_all.csv",
        help="Output CSV path for all scraped corporate office rows",
    )
    parser.add_argument(
        "--city-output",
        default="data/allianz_contact_index_city.csv",
        help="Output CSV path with header country,city,company_type,address,phone",
    )
    args = parser.parse_args()

    scraper = AllianzScraper()
    records = scraper.dedupe_records(scraper.scrape_corporate(args.index_url))
    if not records:
        raise SystemExit("No corporate records scraped")

    city_records = build_city_report(records)
    if not city_records:
        raise SystemExit("No city report rows produced")

    output_path = Path(args.output)
    write_csv(records, output_path)
    city_output_path = Path(args.city_output)
    write_city_report(city_records, city_output_path)
    print(f"wrote {len(records)} rows to {output_path}")
    print(f"wrote {len(city_records)} rows to {city_output_path}")
    print("business units: Allianz Corporate")


if __name__ == "__main__":
    main()
