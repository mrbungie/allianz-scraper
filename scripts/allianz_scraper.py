from __future__ import annotations

import argparse
import csv
import importlib
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


USER_AGENT = "Mozilla/5.0 (compatible; AllianzOfficeScraper/0.1; +https://example.com/bot)"
TIMEOUT = 30
DELAY_SECONDS = 0.25

CORPORATE_INDEX = "https://www.allianz.com/en/about-us/company/contact.html"
COMMERCIAL_INDEX = "https://commercial.allianz.com/global-offices.html"
TECH_INDEX = "https://tech.allianz.com/en/contact.html"
TECH_FALLBACK_PATHS = [
    "/en/contact/australia.html",
    "/en/contact/austria.html",
    "/en/contact/belgium.html",
    "/en/contact/Brazil.html",
    "/en/contact/Colombia.html",
    "/en/contact/Czech-Republic.html",
    "/en/contact/france.html",
    "/en/contact/deutschland.html",
    "/en/contact/hungary.html",
    "/en/contact/india.html",
    "/en/contact/ireland.html",
    "/en/contact/italy.html",
    "/en/contact/mauritius.html",
    "/en/contact/Morocco.html",
    "/en/contact/netherlands.html",
    "/en/contact/romania.html",
    "/en/contact/singapore.html",
    "/en/contact/slovakia.html",
    "/en/contact/spain.html",
    "/en/contact/switzerland.html",
    "/en/contact/bangkok.html",
    "/en/contact/uk.html",
    "/en/contact/spain2.html",
]

NOISE_LINES = {
    "find your contact",
    "more",
    "connect with us",
    "external content cannot be shown without accepting cookies",
    "email us",
    "email",
    "send e-mail",
}

CORPORATE_STOP_PHRASES = {
    "as a customer please find an overview of",
    "products & services",
    "contact allianz life",
    "allianz worldwide",
    "corporate contacts",
    "social media",
    "quick access to allianz usa",
}

COUNTRY_TOKENS = {
    "argentina", "australia", "austria", "belgium", "bermuda", "brazil", "bulgaria", "canada", "china",
    "colombia", "croatia", "czech republic", "france", "germany", "greece", "hong kong", "hungary",
    "india", "indonesia", "ireland", "italy", "italia", "japan", "liechtenstein", "malaysia", "mexico",
    "netherlands", "poland", "portugal", "romania", "singapore", "slovakia", "slovenia", "south africa",
    "south korea", "spain", "sri lanka", "switzerland", "thailand", "turkey", "ukraine", "united kingdom",
    "united states of america", "usa", "uk",
}

PHONE_RE = re.compile(r"\+?[\d][\d\s()\-/]{5,}\d")
POSTCODE_RE = re.compile(r"\b\d{4,6}\b")
WEBSITE_RE = re.compile(r"^(?:https?://|www\.)", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


@dataclass
class OfficeRecord:
    business_unit: str
    country: str
    office_name: str
    office_type: str
    city: str
    address: str
    postcode: str
    phone: str
    email: str
    website: str
    source_url: str
    source_page: str
    notes: str


class AllianzScraper:
    def __init__(self) -> None:
        cloudscraper = importlib.import_module("cloudscraper")
        self.session = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "darwin", "desktop": True})
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        time.sleep(DELAY_SECONDS)
        return BeautifulSoup(response.text, "html.parser")

    def extract_links(self, index_url: str, predicate) -> list[str]:
        soup = self.fetch(index_url)
        seen: set[str] = set()
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = string_attr(anchor.get("href"))
            if not href or href.startswith("#"):
                continue
            absolute = urljoin(index_url, href)
            if absolute in seen or not predicate(absolute):
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    def scrape(self) -> list[OfficeRecord]:
        records: list[OfficeRecord] = []

        corporate_links = self.extract_links(
            CORPORATE_INDEX,
            lambda url: url.startswith("https://www.allianz.com/en/about-us/company/contact/")
            and url.endswith(".html")
            and url != CORPORATE_INDEX,
        )
        for url in corporate_links:
            try:
                records.extend(self.parse_corporate_page(url))
            except requests.HTTPError as exc:
                print(f"skip corporate page {url}: {exc}")

        commercial_links = self.extract_links(
            COMMERCIAL_INDEX,
            lambda url: url.startswith("https://commercial.allianz.com/global-offices/")
            and url.endswith(".html")
            and "#" not in url,
        )
        for url in commercial_links:
            try:
                records.extend(self.parse_commercial_page(url))
            except requests.HTTPError as exc:
                print(f"skip commercial page {url}: {exc}")

        try:
            tech_links = self.extract_links(
                TECH_INDEX,
                lambda url: url.startswith("https://tech.allianz.com/en/contact/")
                and url.lower().endswith(".html")
                and url != TECH_INDEX,
            )
        except requests.HTTPError:
            tech_links = [urljoin(TECH_INDEX, path) for path in TECH_FALLBACK_PATHS]
        for url in tech_links:
            try:
                records.extend(self.parse_tech_page(url))
            except requests.HTTPError as exc:
                print(f"skip technology page {url}: {exc}")

        return self.dedupe_records(records)

    def parse_corporate_page(self, url: str) -> list[OfficeRecord]:
        soup = self.fetch(url)
        page_title = clean_text((soup.title.string if soup.title else "") or "")
        country = page_title.replace("| Allianz", "").strip() or slug_to_country(url)
        body = soup.find("main") or soup.body or soup
        lines = text_lines(body.get_text("\n", strip=True))
        section_titles = [clean_text(h.get_text(" ", strip=True)) for h in body.find_all("h2")]
        section_titles = [title for title in unique(section_titles) if title]

        records: list[OfficeRecord] = []
        for index, title in enumerate(section_titles):
            next_title = section_titles[index + 1] if index + 1 < len(section_titles) else None
            section = slice_lines(lines, title, next_title)
            if not section:
                continue

            if title.lower() == "further contacts":
                for block in split_into_blocks(section[1:]):
                    if normalize_key(block[0]) in COUNTRY_TOKENS | {normalize_key(country), "further contacts"}:
                        continue
                    record = build_record_from_block(
                        business_unit="Allianz Corporate",
                        country=country,
                        office_name=block[0],
                        office_type="contact",
                        block=block[1:],
                        source_url=url,
                        source_page=page_title or country,
                    )
                    if record.address or record.phone or record.website:
                        records.append(record)
                continue

            labeled_entries = parse_labeled_corporate_entries(section[1:])
            if labeled_entries:
                for office_type, address_line in labeled_entries:
                    records.append(
                        build_record_from_block(
                            business_unit="Allianz Corporate",
                            country=country,
                            office_name=title,
                            office_type=office_type,
                            block=[address_line],
                            source_url=url,
                            source_page=page_title or country,
                        )
                    )
            else:
                record = build_record_from_block(
                    business_unit="Allianz Corporate",
                    country=country,
                    office_name=title,
                    office_type="office",
                    block=section[1:],
                    source_url=url,
                    source_page=page_title or country,
                )
                if record.address or record.phone or record.website:
                    records.append(record)

        return records

    def parse_commercial_page(self, url: str) -> list[OfficeRecord]:
        soup = self.fetch(url)
        page_title = clean_text((soup.title.string if soup.title else "") or "")
        h1_tag = soup.find("h1")
        h1 = clean_text(h1_tag.get_text(" ", strip=True) if isinstance(h1_tag, Tag) else "")
        country = extract_trailing_country(h1, "Allianz Commercial in") or slug_to_country(url)

        office_anchor = soup.find(id="office")
        section_root: Tag | BeautifulSoup = soup
        if isinstance(office_anchor, Tag):
            office_parent = office_anchor.find_parent()
            if isinstance(office_parent, Tag):
                next_sibling = office_parent.find_next_sibling()
                if isinstance(next_sibling, Tag):
                    section_root = next_sibling
        section_lines = text_lines(section_root.get_text("\n", strip=True))
        office_lines = slice_lines(section_lines, "Our office") or section_lines

        contact_email = first_email_from_links(soup.select("a[href]"))
        records: list[OfficeRecord] = []
        for block in split_into_blocks(office_lines[1:] if office_lines[:1] == ["Our office"] else office_lines):
            office_name = block[0]
            record = build_record_from_block(
                business_unit="Allianz Commercial",
                country=country,
                office_name=office_name,
                office_type="office",
                block=block[1:],
                source_url=url,
                source_page=page_title or h1 or country,
            )
            if contact_email and not record.email:
                record.email = contact_email
            if record.address:
                records.append(record)

        return records

    def parse_tech_page(self, url: str) -> list[OfficeRecord]:
        soup = self.fetch(url)
        page_title = clean_text((soup.title.string if soup.title else "") or "")
        body = soup.find("main") or soup.body or soup
        lines = text_lines(body.get_text("\n", strip=True))
        first_h2 = body.find("h2") if isinstance(body, Tag) else None
        heading = clean_text(first_h2.get_text(" ", strip=True) if isinstance(first_h2, Tag) else "")
        country = heading or page_title or slug_to_country(url)
        section = slice_lines(lines, country, "Compliance")
        contact_email = first_email_from_links(soup.select("a[href]"))

        records: list[OfficeRecord] = []
        for block in split_into_blocks(section[1:] if section[:1] == [country] else section):
            city = block[0]
            office_name = f"Allianz Technology {city}"
            record = build_record_from_block(
                business_unit="Allianz Technology",
                country=country,
                office_name=office_name,
                office_type="office",
                block=block[1:],
                source_url=url,
                source_page=page_title or country,
                city_hint=city,
            )
            if contact_email and not record.email:
                record.email = contact_email
            if record.address:
                records.append(record)

        return records

    @staticmethod
    def dedupe_records(records: Iterable[OfficeRecord]) -> list[OfficeRecord]:
        deduped: list[OfficeRecord] = []
        seen: set[tuple[str, str, str, str]] = set()
        for record in records:
            key = (
                record.business_unit,
                record.country,
                record.office_name,
                record.address,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        return deduped


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def string_attr(value: object) -> str:
    return value if isinstance(value, str) else ""


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def text_lines(text: str) -> list[str]:
    lines = [clean_text(line) for line in text.splitlines()]
    return [line for line in lines if line and line.lower() not in NOISE_LINES]


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def slug_to_country(url: str) -> str:
    slug = Path(urlparse(url).path).stem
    return slug.replace("-", " ").title()


def slice_lines(lines: list[str], start: str, end: str | None = None) -> list[str]:
    try:
        start_index = lines.index(start)
    except ValueError:
        return []
    if end:
        try:
            end_index = lines.index(end, start_index + 1)
        except ValueError:
            end_index = len(lines)
    else:
        end_index = len(lines)
    return lines[start_index:end_index]


def looks_like_contact_line(line: str) -> bool:
    lower = line.lower()
    return bool(
        PHONE_RE.search(line)
        or WEBSITE_RE.search(line)
        or EMAIL_RE.search(line)
        or lower in {"send e-mail", "email us", "email"}
    )


def looks_like_address_line(line: str) -> bool:
    return bool(re.search(r"\d", line) and re.search(r"[A-Za-z]", line))


def looks_like_country_line(line: str) -> bool:
    return normalize_key(line) in COUNTRY_TOKENS


def is_corporate_stop_line(line: str) -> bool:
    lowered = normalize_key(line)
    return lowered in CORPORATE_STOP_PHRASES


def looks_like_block_start(line: str) -> bool:
    if looks_like_contact_line(line) or looks_like_address_line(line):
        return False
    if len(line) > 90:
        return False
    return bool(re.search(r"[A-Za-z]", line))


def split_into_blocks(lines: Iterable[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not line or line.lower() in NOISE_LINES:
            continue
        if current and looks_like_block_start(line) and any(looks_like_address_line(item) for item in current):
            blocks.append(current)
            current = [line]
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def parse_labeled_corporate_entries(lines: list[str]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    current_label = "office"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        payload: list[str] = []
        for line in buffer:
            if looks_like_contact_line(line):
                continue
            if is_corporate_stop_line(line):
                break
            payload.append(line)
        if not payload:
            buffer = []
            return
        country_line = payload[-1] if looks_like_country_line(payload[-1]) else ""
        address_lines = payload[:-1] if country_line else payload[:]

        groups: list[list[str]] = []
        current_group: list[str] = []
        for item in address_lines:
            if re.search(r"\d", item) and current_group and any(re.search(r"\d", part) for part in current_group):
                groups.append(current_group)
                current_group = [item]
            else:
                current_group.append(item)
        if current_group:
            groups.append(current_group)

        for group in groups:
            group = [item for item in group if item and item.lower() not in NOISE_LINES]
            if not any(re.search(r"\d", item) for item in group):
                continue
            address = ", ".join(group)
            if country_line:
                address = f"{address}, {country_line}"
            entries.append((current_label, address))
        buffer = []

    for line in lines:
        lower = line.lower().rstrip(":")
        if lower in {"registered office", "operational offices", "operational office", "head office", "legal head office", "general management and offices"}:
            flush()
            current_label = lower.replace(" ", "_")
            continue
        if looks_like_contact_line(line):
            continue
        buffer.append(line)
    flush()
    return entries


def decode_cloudflare_email(href: str) -> str:
    if "email-protection#" not in href:
        return ""
    encoded = href.split("email-protection#", 1)[1]
    if len(encoded) < 4:
        return ""
    try:
        key = int(encoded[:2], 16)
        chars = [chr(int(encoded[i : i + 2], 16) ^ key) for i in range(2, len(encoded), 2)]
        return "".join(chars)
    except ValueError:
        return ""


def first_email_from_links(links: Iterable[Tag]) -> str:
    for link in links:
        href = string_attr(link.get("href"))
        if href.startswith("mailto:"):
            return href.replace("mailto:", "", 1).strip()
        decoded = decode_cloudflare_email(href)
        if decoded:
            return decoded
        match = EMAIL_RE.search(link.get_text(" ", strip=True))
        if match:
            return match.group(0)
    return ""


def extract_trailing_country(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text.replace(prefix, "", 1).strip()
    return ""


def extract_city(address: str) -> str:
    country_tokens = [str(token) for token in sorted(COUNTRY_TOKENS, key=lambda token: len(str(token)), reverse=True)]
    cleaned = re.sub(r",?\s*(?:" + "|".join(re.escape(token) for token in country_tokens) + r")$", "", address, flags=re.IGNORECASE)
    match = re.search(r"\b\d{4,6}\s+([A-Za-zÀ-ÿ'\- ]+)\b", cleaned)
    if match:
        return clean_text(match.group(1))
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    for part in reversed(parts):
        if re.search(r"\d", part):
            continue
        if normalize_key(part) in COUNTRY_TOKENS:
            continue
        if len(part) <= 40:
            return part
    for i, part in enumerate(parts):
        if re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", part) and i > 0:
            return parts[i - 1]
    if parts:
        return parts[-1]
    return ""


def build_record_from_block(
    *,
    business_unit: str,
    country: str,
    office_name: str,
    office_type: str,
    block: list[str],
    source_url: str,
    source_page: str,
    city_hint: str = "",
) -> OfficeRecord:
    phones = [line for line in block if PHONE_RE.search(line)]
    websites = [line for line in block if WEBSITE_RE.search(line)]
    emails = [line for line in block if EMAIL_RE.search(line)]
    address_lines = [line for line in block if not looks_like_contact_line(line)]
    address_lines = [line for line in address_lines if not is_corporate_stop_line(line)]
    address = ", ".join(address_lines)
    postcodes = POSTCODE_RE.findall(address)
    postcode = postcodes[-1] if postcodes else ""
    city = city_hint or extract_city(address)
    return OfficeRecord(
        business_unit=business_unit,
        country=country,
        office_name=office_name,
        office_type=office_type,
        city=city,
        address=address,
        postcode=postcode,
        phone=" | ".join(unique(phones)),
        email=" | ".join(unique(emails)),
        website=" | ".join(unique(websites)),
        source_url=source_url,
        source_page=source_page,
        notes="",
    )


def write_csv(records: list[OfficeRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(records[0]).keys()))
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Allianz office data into CSV")
    parser.add_argument("--output", default="data/allianz_offices.csv", help="Output CSV path")
    args = parser.parse_args()

    scraper = AllianzScraper()
    records = scraper.scrape()
    if not records:
        raise SystemExit("No records scraped")

    output_path = Path(args.output)
    write_csv(records, output_path)
    print(f"wrote {len(records)} rows to {output_path}")
    print(f"business units: {', '.join(sorted({record.business_unit for record in records}))}")


if __name__ == "__main__":
    main()
