from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from scripts.allianz_scraper import AllianzScraper, looks_like_website_line


class FakeScraper(AllianzScraper):
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch(self, url: str) -> BeautifulSoup:
        return BeautifulSoup(self.pages[url], "html.parser")


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


if __name__ == "__main__":
    unittest.main()
