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
MAX_FETCH_ATTEMPTS = 3

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
    "back to contacts globally overview",
    "connect with us",
    "external content cannot be shown without accepting cookies",
    "email us",
    "email",
    "send email",
    "send e-mail",
}

CORPORATE_STOP_PHRASES = {
    "as a customer please find an overview of",
    "allianz trade is the trademark used to designate a range of services provided by euler hermes",
    "products & services",
    "contact allianz life",
    "allianz worldwide",
    "corporate contacts",
    "social media",
    "quick access to allianz usa",
}

COUNTRY_TOKENS = {
    "argentina", "australia", "austria", "belgium", "bermuda", "brazil", "bulgaria", "canada", "china",
    "colombia", "croatia", "czech republic", "denmark", "estonia", "finland", "france", "germany", "greece",
    "hong kong", "hungary", "india", "indonesia", "ireland", "italy", "italia", "japan", "latvia",
    "liechtenstein", "lithuania", "luxembourg", "malaysia", "mexico", "netherlands", "norway", "poland",
    "portugal", "romania", "saudi arabia", "senegal", "singapore", "slovakia", "slovenia", "south africa",
    "south korea", "spain", "sri lanka", "switzerland", "thailand", "turkey", "ukraine", "united arab emirates",
    "united kingdom", "united states of america", "usa", "uk",
}

COUNTRY_DISPLAY_NAMES = {
    "argentina": "Argentina",
    "australia": "Australia",
    "austria": "Austria",
    "belgium": "Belgium",
    "bermuda": "Bermuda",
    "brazil": "Brazil",
    "bulgaria": "Bulgaria",
    "canada": "Canada",
    "china": "China",
    "colombia": "Colombia",
    "croatia": "Croatia",
    "czech republic": "Czech Republic",
    "denmark": "Denmark",
    "estonia": "Estonia",
    "finland": "Finland",
    "france": "France",
    "germany": "Germany",
    "greece": "Greece",
    "hong kong": "Hong Kong",
    "hungary": "Hungary",
    "india": "India",
    "indonesia": "Indonesia",
    "ireland": "Ireland",
    "italy": "Italy",
    "italia": "Italy",
    "japan": "Japan",
    "latvia": "Latvia",
    "liechtenstein": "Liechtenstein",
    "lithuania": "Lithuania",
    "luxembourg": "Luxembourg",
    "malaysia": "Malaysia",
    "mexico": "Mexico",
    "netherlands": "Netherlands",
    "norway": "Norway",
    "poland": "Poland",
    "portugal": "Portugal",
    "romania": "Romania",
    "saudi arabia": "Saudi Arabia",
    "senegal": "Senegal",
    "singapore": "Singapore",
    "slovakia": "Slovakia",
    "slovenia": "Slovenia",
    "south africa": "South Africa",
    "south korea": "South Korea",
    "spain": "Spain",
    "sri lanka": "Sri Lanka",
    "switzerland": "Switzerland",
    "thailand": "Thailand",
    "turkey": "Turkey",
    "ukraine": "Ukraine",
    "united arab emirates": "United Arab Emirates",
    "united kingdom": "United Kingdom",
    "united states of america": "United States of America",
    "usa": "USA",
    "uk": "UK",
}

CITY_BLACKLIST = {
    "our",
    "our office",
    "our offices",
    "offices",
    "read more",
    "commercial insights",
    "do you need further information",
    "motor trade",
    "traded via our specialist regional hubs",
    "back to contacts globally overview",
    "for enquiries",
    "products services",
    "products and services",
    "send email",
    "send e mail",
    "send e-mail",
    "email us",
    "get directions",
    "contact us",
    "local compliance officer",
    "nextcare holding wll",
    "ou uma carta de proprio punho para",
    "ou uma carta de próprio punho para",
    "pimco",
    "solunion",
    "colserauto",
    "block a",
    "cityplaza phase four",
    "lg twin towers",
    "technopark trivandrum kerala",
    "offered by allianz insurance plc",
    "the data center construction boom",
    "top 3 business risks in 2026",
}

ADDRESS_SEGMENT_BLACKLIST = {
    "back to contacts globally overview",
    "contact us",
    "email us",
    "find us",
    "for enquiries",
    "get directions",
    "health team helpline",
    "our brand name",
    "postal address",
    "products and services",
    "products services",
    "send email",
    "send e mail",
    "send e-mail",
    "visitor address",
}

ADDRESS_SEGMENT_NOISE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"allianz trade is the trademark used to designate",
        r"all office locations",
        r"all reports",
        r"as a customer please find an overview",
        r"back to contacts",
        r"commercial insights",
        r"do you need further information",
        r"emerging risk trend talk",
        r"find out more",
        r"for queries related to",
        r"if you have any question",
        r"if you have any doubt",
        r"please visit",
        r"privacy",
        r"products and services to suit",
        r"portability of your data",
        r"read more",
        r"through\s+we offer",
        r"website domain names and email addresses changed",
        r"whistleblowing",
        r"your information will be treated confidentially",
        r"\b\d+\s*(?:kb|mb)\b",
        r"\[email protected\]",
        r"@",
        r"www\.",
    )
]

CITY_STOPWORDS = {
    "area",
    "avenue",
    "block",
    "boulevard",
    "branch",
    "building",
    "campus",
    "cedex",
    "center",
    "centre",
    "cours",
    "district",
    "drive",
    "floor",
    "governorate",
    "house",
    "office",
    "park",
    "phase",
    "plaza",
    "province",
    "region",
    "road",
    "rue",
    "square",
    "strasse",
    "straße",
    "street",
    "suite",
    "tower",
    "towers",
}

PHONE_RE = re.compile(r"\+?[\d][\d\s()\-/]{5,}\d")
POSTCODE_RE = re.compile(r"\b\d{4,6}\b")
WEBSITE_RE = re.compile(r"^(?:https?://)?(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:/[^\s]*)?$", re.IGNORECASE)
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


@dataclass
class CityReportRecord:
    country: str
    city: str
    company_type: str
    address: str
    phone: str


class AllianzScraper:
    def __init__(self) -> None:
        cloudscraper = importlib.import_module("cloudscraper")
        self.session = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "darwin", "desktop": True})
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self, url: str) -> BeautifulSoup:
        last_error: requests.RequestException | None = None
        for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
            try:
                response = self.session.get(url, timeout=TIMEOUT)
                response.raise_for_status()
                time.sleep(DELAY_SECONDS)
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as exc:
                last_error = exc
                if attempt == MAX_FETCH_ATTEMPTS:
                    raise
                time.sleep(DELAY_SECONDS * attempt)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Failed to fetch {url}")

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

    def extract_corporate_links(self, index_url: str = CORPORATE_INDEX) -> list[str]:
        return self.extract_links(
            index_url,
            lambda url: url.startswith("https://www.allianz.com/en/about-us/company/contact/")
            and url.endswith(".html")
            and urlparse(url).path != urlparse(CORPORATE_INDEX).path,
        )

    def scrape_corporate(self, index_url: str = CORPORATE_INDEX) -> list[OfficeRecord]:
        records: list[OfficeRecord] = []
        for url in self.extract_corporate_links(index_url):
            try:
                records.extend(self.parse_corporate_page(url))
            except requests.HTTPError as exc:
                print(f"skip corporate page {url}: {exc}")
        return records

    def scrape(
        self,
        *,
        corporate_index_url: str = CORPORATE_INDEX,
        include_corporate: bool = True,
        include_commercial: bool = True,
        include_technology: bool = True,
    ) -> list[OfficeRecord]:
        records: list[OfficeRecord] = []

        if include_corporate:
            records.extend(self.scrape_corporate(corporate_index_url))

        if include_commercial:
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

        if include_technology:
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
                shared_contacts = extract_shared_contact_details(section[1:])
                for office_type, address_line in labeled_entries:
                    records.append(
                        merge_shared_contact_details(
                            build_record_from_block(
                                business_unit="Allianz Corporate",
                                country=country,
                                office_name=title,
                                office_type=office_type,
                                block=[address_line],
                                source_url=url,
                                source_page=page_title or country,
                            ),
                            shared_contacts,
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

        if records:
            return records

        fallback_lines = trim_contact_intro(lines, country)
        for block in split_into_blocks(fallback_lines):
            office_name = block[0]
            office_block = block[1:]
            if looks_like_addressish_block_start(office_name):
                office_name = page_title or country
                office_block = block
            if normalize_key(office_name) in COUNTRY_TOKENS | {normalize_key(country)}:
                continue
            if not block_has_address_content(office_block):
                continue
            record = build_record_from_block(
                business_unit="Allianz Corporate",
                country=country,
                office_name=office_name,
                office_type="office",
                block=office_block,
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

        body = soup.find("main") or soup.body or soup
        section_lines = text_lines(body.get_text("\n", strip=True))
        office_lines = extract_section_lines_by_heading(
            body,
            section_lines,
            lambda title: normalize_key(title) in {"our office", "our offices"},
        )
        if not office_lines:
            office_anchor = soup.find(id="office")
            section_root: Tag | BeautifulSoup = soup
            if isinstance(office_anchor, Tag):
                office_parent = office_anchor.find_parent()
                if isinstance(office_parent, Tag):
                    next_sibling = office_parent.find_next_sibling()
                    if isinstance(next_sibling, Tag):
                        section_root = next_sibling
            section_lines = text_lines(section_root.get_text("\n", strip=True))
            office_lines = slice_lines(section_lines, "Our office") or slice_lines(section_lines, "Our offices") or section_lines

        contact_email = first_email_from_links(soup.select("a[href]"))
        records: list[OfficeRecord] = []
        office_payload = office_lines
        if office_lines and normalize_key(office_lines[0]) in {"our office", "our offices"}:
            office_payload = office_lines[1:]
        for office_name, office_block in split_commercial_office_blocks(office_payload):
            if not office_name or looks_like_addressish_block_start(office_name):
                office_name = h1 or f"Allianz Commercial {country}"
            if not block_has_address_content(office_block):
                continue
            record = build_record_from_block(
                business_unit="Allianz Commercial",
                country=country,
                office_name=office_name,
                office_type="office",
                block=office_block,
                source_url=url,
                source_page=page_title or h1 or country,
            )
            if contact_email and not record.email:
                record.email = contact_email
            if record.address or record.phone or record.website:
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
        looks_like_phone_line(line)
        or looks_like_website_line(line)
        or EMAIL_RE.search(line)
        or lower in {"send e-mail", "email us", "email"}
    )


def looks_like_address_line(line: str) -> bool:
    return bool(re.search(r"\d", line) and re.search(r"[A-Za-z]", line))


def looks_like_country_line(line: str) -> bool:
    normalized = normalize_key(line)
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return normalized in COUNTRY_TOKENS


def extract_phone_numbers(text: str) -> list[str]:
    phones: list[str] = []
    for match in PHONE_RE.finditer(text):
        phone = clean_text(match.group(0).rstrip(".,;:)"))
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 7:
            continue
        if re.search(r"[A-Za-zÀ-ÿ]", phone):
            continue
        phones.append(phone)
    return unique(phones)


def looks_like_phone_line(line: str) -> bool:
    if not extract_phone_numbers(line):
        return False
    if re.search(r"[A-Za-zÀ-ÿ]", line):
        normalized = normalize_key(line)
        return any(token in normalized.split() for token in {"call", "fax", "mobile", "phone", "tel", "telephone"})
    return True


def is_corporate_stop_line(line: str) -> bool:
    lowered = normalize_key(line)
    return lowered in CORPORATE_STOP_PHRASES


def looks_like_block_start(line: str) -> bool:
    if looks_like_contact_line(line) or looks_like_address_line(line) or looks_like_country_line(line):
        return False
    if len(line) > 90:
        return False
    return bool(re.search(r"[A-Za-z]", line))


def looks_like_website_line(line: str) -> bool:
    candidate = clean_text(line).rstrip(".,;)")
    return bool(candidate and " " not in candidate and "@" not in candidate and WEBSITE_RE.fullmatch(candidate))


def looks_like_addressish_block_start(line: str) -> bool:
    return looks_like_address_line(line) or looks_like_country_line(line) or looks_like_website_line(line)


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


def block_has_address_content(lines: Iterable[str]) -> bool:
    return any(looks_like_address_line(line) or looks_like_country_line(line) for line in lines)


def looks_like_commercial_office_heading(line: str) -> bool:
    normalized = normalize_key(line)
    return bool(normalized.endswith(" office") and not looks_like_addressish_block_start(line))


def looks_like_region_code(line: str) -> bool:
    cleaned = clean_text(line)
    return bool(re.fullmatch(r"[A-Z]{2,3}", cleaned)) and not looks_like_country_line(cleaned)


def split_commercial_office_blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    office_name = ""
    current: list[str] = []

    def flush() -> None:
        nonlocal office_name, current
        if office_name or current:
            blocks.append((office_name, current[:]))
        office_name = ""
        current = []

    for line in lines:
        if line.lower() in NOISE_LINES:
            continue
        if looks_like_region_code(line):
            continue
        if looks_like_commercial_office_heading(line):
            flush()
            office_name = line
            continue
        current.append(line)

    flush()
    return [(name, block) for name, block in blocks if name or block]


def trim_contact_intro(lines: list[str], country: str) -> list[str]:
    for index, line in enumerate(lines):
        if "here you will find the contact details" in normalize_key(line):
            return lines[index + 1 :]
    country_key = normalize_key(country)
    last_country_index = -1
    for index, line in enumerate(lines[:20]):
        if normalize_key(line) == country_key:
            last_country_index = index
    if last_country_index >= 0:
        return lines[last_country_index + 1 :]
    return lines


def extract_section_lines_by_heading(
    root: Tag | BeautifulSoup,
    lines: list[str],
    predicate,
    heading_names: tuple[str, ...] = ("h2",),
) -> list[str]:
    titles = [clean_text(tag.get_text(" ", strip=True)) for tag in root.find_all(list(heading_names))]
    titles = [title for title in titles if title]
    for index, title in enumerate(titles):
        if not predicate(title):
            continue
        next_title = titles[index + 1] if index + 1 < len(titles) else None
        return slice_lines(lines, title, next_title) or slice_lines(lines, title)
    return []


def extract_shared_contact_details(lines: Iterable[str]) -> dict[str, list[str]]:
    phones = unique(phone for line in lines for phone in extract_phone_numbers(line) if looks_like_phone_line(line))
    websites = unique(line for line in lines if looks_like_website_line(line))
    emails = unique(line for line in lines if EMAIL_RE.search(line))
    return {"phones": phones, "websites": websites, "emails": emails}


def merge_shared_contact_details(record: OfficeRecord, shared: dict[str, list[str]]) -> OfficeRecord:
    record.phone = " | ".join(unique([*extract_phone_numbers(record.phone), *shared.get("phones", [])]))
    record.website = " | ".join(unique([*split_pipe_values(record.website), *shared.get("websites", [])]))
    record.email = " | ".join(unique([*split_pipe_values(record.email), *shared.get("emails", [])]))
    return record


def split_pipe_values(value: str) -> list[str]:
    return [clean_text(part) for part in value.split("|") if clean_text(part)]


def line_has_postcode(line: str) -> bool:
    return bool(POSTCODE_RE.search(line))


def group_has_postcode(lines: Iterable[str]) -> bool:
    return any(line_has_postcode(line) for line in lines)


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
            if current_group and (
                (looks_like_block_start(item) and any(looks_like_address_line(part) for part in current_group))
                or (group_has_postcode(current_group) and line_has_postcode(item))
            ):
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
    phones = [phone for line in block if looks_like_phone_line(line) for phone in extract_phone_numbers(line)]
    websites = [line for line in block if looks_like_website_line(line)]
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


def normalize_city_key(city: str) -> str:
    return normalize_key(city)


def unique_clean(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def canonical_country_from_text(text: str) -> str:
    normalized = f" {normalize_key(text)} "
    for token, country_name in sorted(COUNTRY_DISPLAY_NAMES.items(), key=lambda item: len(item[0]), reverse=True):
        if f" {token} " in normalized:
            return country_name
    return ""


def resolve_country_for_report(record: OfficeRecord) -> str:
    for candidate in (record.country, record.office_name, record.source_page, record.address, slug_to_country(record.source_url)):
        country = canonical_country_from_text(candidate)
        if country:
            return country
    return clean_text(record.country)


def cleanup_city_candidate(value: str, country: str = "") -> str:
    candidate = clean_text(value)
    if not candidate:
        return ""
    if country:
        candidate = re.sub(rf",?\s*{re.escape(country)}$", "", candidate, flags=re.IGNORECASE).strip(" ,-–")
    candidate = candidate.split("|")[-1].strip()
    candidate = re.sub(r"^\d{4,6}(?:-\d{2,4})?\s+", "", candidate)
    candidate = re.sub(r",?\s*[A-Z]{1,3}\s+\d{4,6}(?:-\d{4})?$", "", candidate)
    candidate = re.sub(r"\b\d{4,6}(?:-\d{4})?\b", "", candidate)
    candidate = re.sub(r"^[^A-Za-zÀ-ÿ]+", "", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" ,-–")
    return candidate


def looks_like_city_candidate(value: str, country: str = "") -> bool:
    candidate = cleanup_city_candidate(value, country)
    normalized = normalize_key(candidate)
    country_normalized = normalize_key(country)
    if not candidate or not normalized:
        return False
    if normalized in CITY_BLACKLIST or normalized in COUNTRY_TOKENS:
        return False
    if country and normalized == country_normalized:
        return False
    if country_normalized and (normalized.startswith(country_normalized) or country_normalized.startswith(normalized)):
        return False
    if len(candidate) > 40 or len(candidate) < 3:
        return False
    if re.search(r"\d", candidate):
        return False
    if re.search(r"[,/:;&]", candidate):
        return False
    if not re.search(r"[A-Za-zÀ-ÿ]", candidate):
        return False
    if all(len(token) <= 1 for token in normalized.split()):
        return False
    if any(stopword in normalized.split() for stopword in CITY_STOPWORDS):
        return False
    if re.search(r"\b(?:risk|insurance|reinsurance|solutions|solution|infrastructure|registration|registered|limited|ltd|plc|llc|inc|company|benefits|holding|services|enquiries|compliance|global|local)\b", normalized):
        return False
    if re.search(r"\b(?:ag|sa|se|sas|sro|gmbh|kg|bv|nv|spa|srl|sarl|llp)\b", normalized):
        return False
    if "allianz" in normalized:
        return False
    return True


def split_address_segments(address: str) -> list[str]:
    return [clean_text(part) for part in re.split(r"[,|]", address) if clean_text(part)]


def is_noise_address_segment(segment: str) -> bool:
    normalized = normalize_key(segment)
    if not normalized:
        return True
    if normalized in ADDRESS_SEGMENT_BLACKLIST:
        return True
    if any(pattern.search(segment) for pattern in ADDRESS_SEGMENT_NOISE_PATTERNS):
        return True
    return False


def clean_address_for_report(address: str) -> str:
    kept: list[str] = []
    for segment in split_address_segments(address):
        if is_noise_address_segment(segment):
            continue
        segment = clean_text(segment)
        if segment:
            kept.append(segment)
    return ", ".join(unique_clean(kept))


def looks_like_address_for_report(address: str) -> bool:
    if not address:
        return False
    parts = split_address_segments(address)
    if len(parts) < 2 or len(parts) > 12:
        return False
    if any(pattern.search(address) for pattern in ADDRESS_SEGMENT_NOISE_PATTERNS):
        return False
    return any(re.search(r"\d", part) for part in parts)


def extract_phone_numbers_for_report(text: str) -> list[str]:
    return unique_clean(extract_phone_numbers(text))


def clean_phone_for_report(phone: str) -> str:
    return " | ".join(extract_phone_numbers_for_report(phone))


def extract_city_candidates_from_address(address: str, country: str) -> list[str]:
    parts = split_address_segments(address)
    candidates: list[str] = []
    for part in reversed(parts):
        candidate = cleanup_city_candidate(part, country)
        if looks_like_city_candidate(candidate, country):
            candidates.append(candidate)
    postcode_match = re.search(r"\b\d{4,6}\s+([A-Za-zÀ-ÿ'\- ]+)\b", address)
    if postcode_match:
        candidate = cleanup_city_candidate(postcode_match.group(1), country)
        if looks_like_city_candidate(candidate, country):
            candidates.append(candidate)
    return unique_clean(candidates)


def city_candidate_score(candidate: str, source: str, cleaned_address: str, record: OfficeRecord, country: str) -> int:
    score = 0
    normalized_candidate = normalize_key(candidate)
    normalized_address = normalize_key(cleaned_address)
    if source == "address":
        score += 4
    elif source == "record_city":
        score += 2
    else:
        score += 3
    if normalized_candidate and normalized_candidate in normalized_address:
        score += 2
    if candidate == record.office_name:
        score += 1
    if candidate == record.city:
        score += 1
    if re.search(r"[()\-]", candidate):
        score -= 1
    if country and normalize_key(candidate) == normalize_key(country):
        score -= 10
    return score


def resolve_city_for_report(record: OfficeRecord, country: str) -> str:
    cleaned_address = clean_address_for_report(record.address)
    candidates: list[tuple[int, str]] = []
    for source, raw_candidate in (("office_name", record.office_name), ("record_city", record.city)):
        cleaned = cleanup_city_candidate(raw_candidate, country)
        if looks_like_city_candidate(cleaned, country):
            candidates.append((city_candidate_score(cleaned, source, cleaned_address, record, country), cleaned))
    for raw_candidate in extract_city_candidates_from_address(cleaned_address, country):
        cleaned = cleanup_city_candidate(raw_candidate, country)
        if looks_like_city_candidate(cleaned, country):
            candidates.append((city_candidate_score(cleaned, "address", cleaned_address, record, country), cleaned))
    if not candidates:
        return ""
    return max(candidates, key=lambda item: (item[0], -len(item[1]), item[1]))[1]


def office_type_priority(office_type: str) -> int:
    priorities = {
        "general_management_and_offices": 7,
        "legal_head_office": 6,
        "head_office": 5,
        "registered_office": 4,
        "operational_offices": 3,
        "operational_office": 3,
        "office": 2,
        "contact": 1,
    }
    return priorities.get(office_type, 0)


def business_unit_priority(business_unit: str) -> int:
    priorities = {
        "Allianz Corporate": 3,
        "Allianz Commercial": 2,
        "Allianz Technology": 1,
    }
    return priorities.get(business_unit, 0)


def office_name_priority(record: OfficeRecord) -> int:
    label = normalize_key(f"{record.office_name} {record.office_type}")
    score = 0
    if "head office" in label:
        score += 4
    if "registered office" in label:
        score += 3
    if "general management" in label:
        score += 3
    if "allianz" in label:
        score += 1
    if looks_like_city_candidate(record.office_name, record.country):
        score += 2
    return score


def city_report_sort_key(record: OfficeRecord) -> tuple[int, int, int, int, int, int]:
    cleaned_phone = clean_phone_for_report(record.phone)
    cleaned_address = clean_address_for_report(record.address)
    return (
        office_type_priority(record.office_type),
        office_name_priority(record),
        business_unit_priority(record.business_unit),
        int(bool(cleaned_phone)),
        int(looks_like_address_for_report(cleaned_address)),
        len(cleaned_address),
    )


def build_city_report(records: Iterable[OfficeRecord]) -> list[CityReportRecord]:
    selected: dict[tuple[str, str], OfficeRecord] = {}
    for record in records:
        country = resolve_country_for_report(record)
        cleaned_address = clean_address_for_report(record.address)
        if not looks_like_address_for_report(cleaned_address):
            continue
        city = resolve_city_for_report(record, country)
        if not city:
            continue
        key = (country, normalize_city_key(city))
        current = selected.get(key)
        if current is None or city_report_sort_key(record) > city_report_sort_key(current):
            selected[key] = record

    report: list[CityReportRecord] = []
    for (country, _), record in sorted(selected.items(), key=lambda item: (item[0][0], resolve_city_for_report(item[1], item[0][0]).lower(), item[1].business_unit.lower())):
        city = resolve_city_for_report(record, country)
        cleaned_address = clean_address_for_report(record.address)
        report.append(
            CityReportRecord(
                country=country,
                city=city,
                company_type=f"{record.business_unit} {city}",
                address=cleaned_address,
                phone=clean_phone_for_report(record.phone),
            )
        )
    return report


def write_city_report(records: list[CityReportRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(records[0]).keys()))
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


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
