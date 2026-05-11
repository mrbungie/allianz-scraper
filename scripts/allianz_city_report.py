from __future__ import annotations

import argparse
import csv
from pathlib import Path

from allianz_scraper import OfficeRecord, build_city_report, write_city_report


def read_office_records(input_path: Path) -> list[OfficeRecord]:
    with input_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [OfficeRecord(**{field: row.get(field, "") for field in OfficeRecord.__dataclass_fields__}) for row in reader]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a city-level Allianz report from the scraped CSV")
    parser.add_argument("--input", default="data/allianz_offices.csv", help="Input CSV from scripts/allianz_scraper.py")
    parser.add_argument("--output", default="data/allianz_city_offices.csv", help="Output CSV path")
    args = parser.parse_args()

    records = read_office_records(Path(args.input))
    if not records:
        raise SystemExit("No office rows found in input CSV")

    city_records = build_city_report(records)
    if not city_records:
        raise SystemExit("No city report rows produced")

    output_path = Path(args.output)
    write_city_report(city_records, output_path)
    print(f"wrote {len(city_records)} rows to {output_path}")


if __name__ == "__main__":
    main()
