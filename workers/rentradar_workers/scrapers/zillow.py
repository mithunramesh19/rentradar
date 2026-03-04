"""Zillow scraper — Playwright + stealth."""

from __future__ import annotations

import json
import logging
import random
import time

from bs4 import BeautifulSoup, Tag

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import BaseScraper, RawListing, SourceConfig
from rentradar_workers.scrapers.tasks import register_scraper

logger = logging.getLogger(__name__)

# ── CSS Selectors ────────────────────────────────────────────────────

SEL_CARD = "article[data-test='property-card']"
SEL_CARD_LINK = "a[data-test='property-card-link']"
SEL_CARD_PRICE = "[data-test='property-card-price']"
SEL_CARD_ADDRESS = "address[data-test='property-card-addr']"
SEL_CARD_BEDS = "abbr[aria-label*='bed']"  # e.g. "2 bd"
SEL_CARD_BATHS = "abbr[aria-label*='bath']"
SEL_CARD_SQFT = "abbr[aria-label*='sqft']"
SEL_CARD_IMG = "img[data-test='property-card-img']"

# Detail page
SEL_DETAIL_PRICE = "span[data-testid='price']"
SEL_DETAIL_ADDRESS = "h1[data-testid='bdp-address']"
SEL_DETAIL_BEDS = "span[data-testid='bed-bath-item']:nth-of-type(1)"
SEL_DETAIL_BATHS = "span[data-testid='bed-bath-item']:nth-of-type(2)"
SEL_DETAIL_SQFT = "span[data-testid='bed-bath-item']:nth-of-type(3)"
SEL_DETAIL_DESC = "div[data-testid='description-text']"

ZILLOW_NYC_URL = "https://www.zillow.com/new-york-ny/rentals/"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
]


class ZillowScraper(BaseScraper):
    """Zillow rental scraper using Playwright with stealth settings."""

    def __init__(self, config: SourceConfig | None = None) -> None:
        if config is None:
            config = SourceConfig(
                source=ListingSource.ZILLOW,
                base_url=ZILLOW_NYC_URL,
                rate_limit_seconds=5.0,
                max_pages=10,
                timeout_seconds=30,
            )
        super().__init__(config)

    def scrape(self) -> list[RawListing]:
        """Scrape Zillow using Playwright with stealth."""
        from playwright.sync_api import sync_playwright

        all_listings: list[RawListing] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
            )
            # Stealth: remove webdriver flag
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            """)

            page = context.new_page()

            for page_num in range(1, self.config.max_pages + 1):
                self.throttle()
                url = f"{self.config.base_url}{page_num}_p/" if page_num > 1 else self.config.base_url

                try:
                    page.goto(url, timeout=self.config.timeout_seconds * 1000)
                    page.wait_for_selector(SEL_CARD, timeout=10000)
                    time.sleep(random.uniform(1, 3))

                    html = page.content()
                    page_listings = self.parse_listing_page(html)
                    if not page_listings:
                        break
                    all_listings.extend(page_listings)
                    self.logger.info(
                        "Page %d: %d listings (total %d)",
                        page_num,
                        len(page_listings),
                        len(all_listings),
                    )
                except Exception:
                    self.logger.exception("Failed on Zillow page %d", page_num)
                    break

            browser.close()

        return all_listings

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse Zillow search page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(SEL_CARD)
        listings: list[RawListing] = []

        for card in cards:
            try:
                listings.append(self._parse_card(card))
            except Exception:
                self.logger.debug("Failed to parse Zillow card", exc_info=True)

        return listings

    def parse_listing_detail(self, html: str, url: str) -> RawListing:
        """Parse Zillow detail page."""
        soup = BeautifulSoup(html, "html.parser")

        def text(sel: str) -> str:
            el = soup.select_one(sel)
            return el.get_text(strip=True) if el else ""

        return RawListing(
            source=ListingSource.ZILLOW,
            source_url=url,
            address=text(SEL_DETAIL_ADDRESS),
            price=text(SEL_DETAIL_PRICE),
            bedrooms=text(SEL_DETAIL_BEDS),
            bathrooms=text(SEL_DETAIL_BATHS),
            sqft=text(SEL_DETAIL_SQFT),
            description=text(SEL_DETAIL_DESC),
        )

    def _parse_card(self, card: Tag) -> RawListing:
        """Parse a single Zillow property card."""
        def _text(sel: str) -> str:
            el = card.select_one(sel)
            return el.get_text(strip=True) if el else ""

        def _attr(sel: str, attr: str) -> str:
            el = card.select_one(sel)
            return el.get(attr, "") if el else ""

        address = _text(SEL_CARD_ADDRESS)
        href = _attr(SEL_CARD_LINK, "href")
        if href and not href.startswith("http"):
            href = f"https://www.zillow.com{href}"

        img_url = _attr(SEL_CARD_IMG, "src")

        return RawListing(
            source=ListingSource.ZILLOW,
            source_url=href or f"https://zillow.com#{address}",
            address=address,
            price=_text(SEL_CARD_PRICE),
            bedrooms=_text(SEL_CARD_BEDS),
            bathrooms=_text(SEL_CARD_BATHS),
            sqft=_text(SEL_CARD_SQFT),
            image_urls=[img_url] if img_url else [],
        )


register_scraper(ListingSource.ZILLOW, ZillowScraper)
