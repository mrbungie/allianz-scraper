from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from scripts.allianz_scraper import AllianzScraper, OfficeRecord, build_city_report, looks_like_website_line


class FakeScraper(AllianzScraper):
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch(self, url: str) -> BeautifulSoup:
        return BeautifulSoup(self.pages[url], "html.parser")


class RouteFakeScraper(AllianzScraper):
    def __init__(self, corporate_links: list[str], records_by_url: dict[str, list[OfficeRecord]]) -> None:
        self.corporate_links = corporate_links
        self.records_by_url = records_by_url

    def extract_corporate_links(self, index_url: str = "") -> list[str]:
        return self.corporate_links

    def parse_corporate_page(self, url: str) -> list[OfficeRecord]:
        return self.records_by_url[url]

    def extract_links(self, index_url: str, predicate):
        raise AssertionError("unexpected non-corporate link extraction")


class AllianzScraperTests(unittest.TestCase):
    def test_parse_corporate_page_falls_back_when_no_h2_sections(self) -> None:
        url = "https://www.allianz.com/en/about-us/company/contact/denmark.html"
        scraper = FakeScraper(
            {
                url: """
                <html>
                  <head><title>Denmark | Allianz</title></head>
                  <body>
                    <main>
                      <h1>Denmark</h1>
                      <p>Here you will find the contact details for the Allianz entities in the country.</p>
                      <p>Allianz Commercial</p>
                      <p>Pilestraede 58</p>
                      <p>Copenhagen, 1112</p>
                      <p>Denmark</p>
                      <p>commercial.allianz.com</p>
                      <p>Allianz Partners Nordic and Baltic Region</p>
                      <p>Poeldijkstraat 4</p>
                      <p>1059 VM Amsterdam</p>
                      <p>The Netherlands</p>
                      <p>www.allianz-partners.com</p>
                      <p>Allianz Trade in Denmark</p>
                      <p>Møntergade 5</p>
                      <p>1116 København K</p>
                      <p>Denmark</p>
                      <p>+45 88 33 33 88</p>
                      <p>www.allianz-trade.com</p>
                    </main>
                  </body>
                </html>
                """,
            }
        )

        records = scraper.parse_corporate_page(url)

        self.assertEqual(3, len(records))
        self.assertEqual("Allianz Commercial", records[0].office_name)
        self.assertEqual("Pilestraede 58, Copenhagen, 1112, Denmark", records[0].address)
        self.assertEqual("commercial.allianz.com", records[0].website)
        self.assertEqual("Allianz Trade in Denmark", records[2].office_name)
        self.assertEqual("+45 88 33 33 88", records[2].phone)

    def test_parse_commercial_page_limits_to_office_section(self) -> None:
        url = "https://commercial.allianz.com/global-offices/united-states-of-america.html"
        scraper = FakeScraper(
            {
                url: """
                <html>
                  <head><title>Business insurance in the United States - Allianz Commercial USA</title></head>
                  <body>
                    <main>
                      <h1>Allianz Commercial in the United States</h1>
                      <h2>Allianz Commercial offerings in the United States</h2>
                      <p>Noise before office section</p>
                      <h2>Our offices</h2>
                      <h3>Alpharetta office</h3>
                      <p>3655 Brookside Parkway</p>
                      <p>Alpharetta, 30022</p>
                      <p>USA</p>
                      <h3>New York office</h3>
                      <p>28 Liberty Street</p>
                      <p>New York, 10005</p>
                      <p>USA</p>
                      <h2>Further information</h2>
                      <p>All reports</p>
                      <p>Should not be scraped</p>
                    </main>
                  </body>
                </html>
                """,
            }
        )

        records = scraper.parse_commercial_page(url)

        self.assertEqual(2, len(records))
        self.assertEqual(["Alpharetta office", "New York office"], [record.office_name for record in records])
        self.assertEqual("3655 Brookside Parkway, Alpharetta, 30022, USA", records[0].address)

    def test_parse_commercial_page_handles_single_unnamed_office(self) -> None:
        url = "https://commercial.allianz.com/global-offices/portugal.html"
        scraper = FakeScraper(
            {
                url: """
                <html>
                  <head><title>Business insurance company in Portugal - Allianz Commercial</title></head>
                  <body>
                    <main>
                      <h1>Allianz Commercial in Portugal</h1>
                      <h2>Our office</h2>
                      <p>R. Andrade Corvo 32</p>
                      <p>1069-014 Lisboa</p>
                      <p>Portugal</p>
                    </main>
                  </body>
                </html>
                """,
            }
        )

        records = scraper.parse_commercial_page(url)

        self.assertEqual(1, len(records))
        self.assertEqual("Allianz Commercial in Portugal", records[0].office_name)
        self.assertEqual("R. Andrade Corvo 32, 1069-014 Lisboa, Portugal", records[0].address)

    def test_website_detection_accepts_bare_domains(self) -> None:
        self.assertTrue(looks_like_website_line("commercial.allianz.com"))
        self.assertTrue(looks_like_website_line("www.allianz-trade.com"))
        self.assertFalse(looks_like_website_line("123 Main Street"))

    def test_scrape_corporate_uses_custom_index_links(self) -> None:
        germany = "https://www.allianz.com/en/about-us/company/contact/germany.html"
        france = "https://www.allianz.com/en/about-us/company/contact/france.html"
        scraper = RouteFakeScraper(
            corporate_links=[germany, france],
            records_by_url={
                germany: [
                    OfficeRecord(
                        business_unit="Allianz Corporate",
                        country="Germany",
                        office_name="Allianz Germany",
                        office_type="office",
                        city="Munich",
                        address="Koeniginstrasse 28, 80802 Munich, Germany",
                        postcode="80802",
                        phone="+49 89 123456",
                        email="",
                        website="",
                        source_url=germany,
                        source_page="Germany | Allianz",
                        notes="",
                    )
                ],
                france: [
                    OfficeRecord(
                        business_unit="Allianz Corporate",
                        country="France",
                        office_name="Allianz France",
                        office_type="office",
                        city="Paris",
                        address="1 Cours Michelet, 92076 Paris, France",
                        postcode="92076",
                        phone="+33 1 23456789",
                        email="",
                        website="",
                        source_url=france,
                        source_page="France | Allianz",
                        notes="",
                    )
                ],
            },
        )

        records = scraper.scrape(corporate_index_url="https://www.allianz.com/en/about-us/company/contact.html", include_commercial=False, include_technology=False)

        self.assertEqual(["Germany", "France"], [record.country for record in records])

    def test_parse_corporate_page_applies_shared_phone_to_each_city_record(self) -> None:
        url = "https://www.allianz.com/en/about-us/company/contact/italy.html"
        scraper = FakeScraper(
            {
                url: """
                <html>
                  <head><title>Italy | Allianz</title></head>
                  <body>
                    <main>
                      <h1>Italy</h1>
                      <h2>Allianz S.p.A.</h2>
                      <p>Registered office:</p>
                      <p>Piazza Tre Torri, 3 – 20145 Milano</p>
                      <p>Italy</p>
                      <p>Operational offices:</p>
                      <p>Piazza Tre Torri, 3 - 20145 Milano</p>
                      <p>Largo Ugo Irneri, 1 - 34123 Trieste</p>
                      <p>Italy</p>
                      <p>+39 02 721 61</p>
                      <p>+39 02 2216 5000</p>
                      <p>www.allianz.it</p>
                    </main>
                  </body>
                </html>
                """,
            }
        )

        records = scraper.parse_corporate_page(url)

        self.assertEqual(3, len(records))
        self.assertTrue(all(record.phone == "+39 02 721 61 | +39 02 2216 5000" for record in records))
        city_rows = build_city_report(records)
        self.assertEqual(["Milano", "Trieste"], [row.city for row in city_rows])
        self.assertTrue(all(row.phone == "+39 02 721 61 | +39 02 2216 5000" for row in city_rows))


if __name__ == "__main__":
    unittest.main()
