"""Craigslist scraper — requests + BeautifulSoup."""

from __future__ import annotations

import logging
import random

import requests
from bs4 import BeautifulSoup, Tag

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import BaseScraper, RawListing, SourceConfig
from rentradar_workers.scrapers.tasks import register_scraper

logger = logging.getLogger(__name__)

# ── CSS Selectors ────────────────────────────────────────────────────

SEL_RESULT = "li.cl-static-search-result"
SEL_TITLE = ".title"
SEL_PRICE = ".price"
SEL_DETAILS = ".details"
SEL_POSTING_LINK = "a.posting-title"
SEL_POST_BODY = "section#postingbody"
SEL_MAP_ATTRS = "#map"  # data-latitude, data-longitude
SEL_ATTRGROUP = "p.attrgroup span"

# Craigslist NYC subdomains
NYC_CL_URL = "https://newyork.craigslist.org"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]


class CraigslistScraper(BaseScraper):
    """Craigslist apartment scraper using requests + BeautifulSoup."""

    def __init__(self, config: SourceConfig | None = None) -> None:
        if config is None:
            config = SourceConfig(
                source=ListingSource.CRAIGSLIST,
                base_url=NYC_CL_URL,
                rate_limit_seconds=2.0,
                max_pages=20,
                timeout_seconds=20,
            )
        super().__init__(config)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def scrape(self) -> list[RawListing]:
        """Scrape CL search results pages."""
        all_listings: list[RawListing] = []
        offset = 0
        per_page = 120  # CL default page size

        for page in range(1, self.config.max_pages + 1):
            self.throttle()
            url = f"{self.config.base_url}/search/apa#search=1~gallery~{offset}~0"
            try:
                resp = self._session.get(url, timeout=self.config.timeout_seconds)
                resp.raise_for_status()
            except requests.RequestException:
                self.logger.exception("Failed to fetch page %d", page)
                break

            page_listings = self.parse_listing_page(resp.text)
            if not page_listings:
                break
            all_listings.extend(page_listings)
            self.logger.info("Page %d: %d listings (total %d)", page, len(page_listings), len(all_listings))
            offset += per_page

        return all_listings

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse CL search page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        results = soup.select(SEL_RESULT)
        listings: list[RawListing] = []

        for result in results:
            try:
                listings.append(self._parse_result(result))
            except Exception:
                self.logger.debug("Failed to parse CL result", exc_info=True)

        return listings

    def parse_listing_detail(self, html: str, url: str) -> RawListing:
        """Parse a CL posting detail page."""
        soup = BeautifulSoup(html, "html.parser")

        title_el = soup.select_one("#titletextonly")
        title = title_el.get_text(strip=True) if title_el else ""

        price_el = soup.select_one(".price")
        price = price_el.get_text(strip=True) if price_el else ""

        body_el = soup.select_one(SEL_POST_BODY)
        description = body_el.get_text(strip=True) if body_el else ""

        # Lat/lng from map element
        map_el = soup.select_one(SEL_MAP_ATTRS)
        lat = map_el.get("data-latitude", "") if map_el else ""
        lng = map_el.get("data-longitude", "") if map_el else ""

        # Attributes: beds, baths, sqft from attrgroup
        beds = ""
        baths = ""
        sqft = ""
        for span in soup.select(SEL_ATTRGROUP):
            text = span.get_text(strip=True).lower()
            if "br" in text and beds == "":
                beds = text
            elif "ba" in text and baths == "":
                baths = text
            elif "ft" in text and sqft == "":
                sqft = text

        return RawListing(
            source=ListingSource.CRAIGSLIST,
            source_url=url,
            title=title,
            price=price,
            bedrooms=beds,
            bathrooms=baths,
            sqft=sqft,
            description=description,
            detail_data={"lat": lat, "lng": lng},
        )

    def _parse_result(self, result: Tag) -> RawListing:
        """Parse a single CL search result element."""
        title_el = result.select_one(SEL_TITLE)
        title = title_el.get_text(strip=True) if title_el else ""

        price_el = result.select_one(SEL_PRICE)
        price = price_el.get_text(strip=True) if price_el else ""

        link_el = result.select_one("a")
        href = link_el.get("href", "") if link_el else ""
        if href and not href.startswith("http"):
            href = f"{self.config.base_url}{href}"

        details_el = result.select_one(SEL_DETAILS)
        details_text = details_el.get_text(strip=True) if details_el else ""

        return RawListing(
            source=ListingSource.CRAIGSLIST,
            source_url=href,
            title=title,
            price=price,
            description=details_text,
        )


register_scraper(ListingSource.CRAIGSLIST, CraigslistScraper)
