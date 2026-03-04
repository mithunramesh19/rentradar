"""StreetEasy scraper — ported from ~/Desktop/ApartmentScraper/scrape_streeteasy.py.

Uses Selenium + selenium-stealth for anti-detection. Extends BaseScraper ABC.
"""

from __future__ import annotations

import logging
import os
import random
import shutil
import time
from datetime import datetime, timedelta
from glob import glob
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import (
    BaseScraper,
    BlockedError,
    RawListing,
    SourceConfig,
    parse_float,
    parse_int,
    parse_price,
)
from rentradar_workers.scrapers.tasks import register_scraper

logger = logging.getLogger(__name__)

# ── CSS Selectors (ported from ApartmentScraper) ─────────────────────

# Search results page
SEL_LISTING_CARD = "div[data-testid='listing-card']"
SEL_TITLE = "p.ListingDescription-module__title___B9n4Z"
SEL_ADDRESS = "a.ListingDescription-module__addressTextAction___xAFZJ"
SEL_PRICE = "span.PriceInfo-module__price___pKybg"
SEL_BASE_RENT = "button.PriceInfo-module__baseRent___jHKuz"
SEL_PRICE_TAG = "div.PriceInfo-module__priceInfoTag___pVv0Z span[data-testid='tag-text']"
SEL_BEDS_BATHS_SQFT = "ul.BedsBathsSqft-module__list___mj--s"
SEL_BBS_TEXT = ".BedsBathsSqft-module__text___lnveO"
SEL_LISTED_BY = "p.ListingBy-module__ListingBy___pBXCl"
SEL_IMAGE = "img.CardImage-module__cardImage___cirIN"

# Detail page
SEL_DETAIL_ADDRESS = 'h1[data-testid="address"]'
SEL_DETAIL_LISTED_BY = 'p[data-testid="listing-by"]'
SEL_DETAIL_AVAILABILITY = 'div[data-testid="rentalListingSpec-available"] .Body_base_gyzqw'
SEL_DETAIL_DOM = 'div[data-testid="rentalListingSpec-daysOnMarket"] .Body_base_gyzqw'
SEL_DETAIL_LAST_CHANGE = (
    'div[data-testid="rentalListingSpec-latPriceChanged"] .Body_base_gyzqw'
)
SEL_PRICE_HISTORY_ROW = 'div[data-testid="priceHistoryTable"] table tbody tr'
SEL_ABOUT = (
    "section[data-testid='about-section'] "
    ".ListingDescription_shortDescription__ySvRK"
)
SEL_BUILDING_SECTION = 'section[data-testid="about-building-section"]'
SEL_BUILDING_ADDRESS = "p.AboutBuildingSection_address__TdYEX"
SEL_BUILDING_INFO = ".AboutBuildingSection_infoItem__CIIZZ span"
SEL_BUILDING_UNITS = '.AboutBuildingSection_linkList__8WusC a[href*="rentals"]'

# Agent cards
SEL_AGENT_CONTAINER = (
    "div.styled__CardsContainer-sc-1tbduzj-2 > div.styled__Container-sc-1lwfbzj-0"
)
SEL_AGENT_NAME = "a.styled__AgentLink-sc-1lwfbzj-2"
SEL_AGENT_TEXT = "p.styled__Text-sc-1lwfbzj-4"
SEL_AGENT_PHONE_BTN = "button.styled__ShowPhone-sc-1lwfbzj-7"
SEL_AGENT_PHONE_TEXT = ".styled__PhoneContainer-sc-1lwfbzj-5 .Body_base_gyzqw"

# ── Default search URLs ──────────────────────────────────────────────

DEFAULT_SEARCH_URLS = [
    "https://streeteasy.com/for-rent/nyc?sort_by=listed_desc",
]


# ── Block detection XPaths ───────────────────────────────────────────

BLOCK_XPATHS = [
    "//h1[contains(text(), 'Access Denied')]",
    "//div[contains(text(), 'Please try again')]",
    "//div[contains(text(), 'suspicious activity')]",
    "//div[contains(text(), 'Access to this page has been denied')]",
    "//div[contains(text(), 'You are being rate limited')]",
    "//h1[contains(text(), 'Rate Limited')]",
    "//h1[contains(text(), 'Please Wait')]",
    "//h1[contains(text(), 'Just a moment')]",
    "//*[contains(text(), 'please prove')]",
    "//*[contains(text(), 'human verification')]",
    "//*[contains(text(), 'checking if the site connection is secure')]",
    "//*[contains(text(), 'checking your browser')]",
    "//*[contains(text(), 'Too Many Requests')]",
    "//*[contains(text(), 'temporarily blocked')]",
    "//*[contains(text(), 'unusual traffic')]",
    "//*[contains(text(), 'automated access')]",
]


# ── Helper functions ─────────────────────────────────────────────────


def _check_blocked(driver: webdriver.Chrome) -> tuple[bool, str | None]:
    """Check if StreetEasy or Cloudflare is blocking us."""
    try:
        for xpath in BLOCK_XPATHS:
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                logger.warning("Detected blocking via: %s", xpath)
                return True, "text_block"
        return False, None
    except Exception:
        logger.debug("Error checking for blocks", exc_info=True)
        return False, "error"


def cleanup_old_profiles(max_age_hours: float = 0.5) -> None:
    """Remove Chrome profiles older than max_age_hours."""
    try:
        pattern = os.path.join(os.getcwd(), "chrome_profile_*")
        now = datetime.now()
        for profile_dir in glob(pattern):
            try:
                created = datetime.fromtimestamp(os.path.getctime(profile_dir))
                if now - created > timedelta(hours=max_age_hours):
                    shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception:
                logger.debug("Error cleaning profile %s", profile_dir, exc_info=True)
    except Exception:
        logger.debug("Error in cleanup process", exc_info=True)


def get_driver() -> webdriver.Chrome:
    """Initialize Chrome with selenium-stealth anti-detection.

    Ported from ApartmentScraper get_driver() with:
    - Randomized user agent (platform, Chrome version)
    - Randomized WebGL vendor/renderer
    - Anti-automation flags
    - Unique profile per session
    """
    chrome_opts = Options()

    # Randomized user agent
    platforms = [
        ("Windows NT 10.0", "Win64; x64"),
        ("Macintosh", "Intel Mac OS X 10_15_7"),
        ("X11", "Linux x86_64"),
    ]
    platform, architecture = random.choice(platforms)
    major = random.randint(110, 122)
    user_agent = (
        f"Mozilla/5.0 ({platform}; {architecture}) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.{random.randint(0, 9999)}.{random.randint(0, 999)} "
        "Safari/537.36"
    )

    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument(f"--user-agent={user_agent}")
    chrome_opts.add_argument("--start-maximized")
    chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
    chrome_opts.add_argument("--disable-notifications")
    chrome_opts.add_argument("--disable-extensions")
    chrome_opts.add_argument("--no-first-run")
    chrome_opts.add_argument("--no-default-browser-check")

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "webrtc.ip_handling_policy": "disable_non_proxied_udp",
        "webrtc.multiple_routes_enabled": False,
        "webrtc.nonproxied_udp_enabled": False,
    }
    chrome_opts.add_experimental_option("prefs", prefs)
    chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_opts.add_experimental_option("useAutomationExtension", False)

    # Unique profile directory
    profile_dir = os.path.join(
        os.getcwd(),
        f"chrome_profile_{random.randint(10000, 99999)}_{int(time.time())}",
    )
    os.makedirs(profile_dir, exist_ok=True)
    chrome_opts.add_argument(f"--user-data-dir={profile_dir}")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_opts)

        # Stealth with random WebGL
        webgl_vendors = [
            ("Google Inc.", "ANGLE (Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0)"),
            ("Intel Inc.", "Intel Iris OpenGL Engine"),
            ("NVIDIA Corporation", "NVIDIA GeForce GTX"),
        ]
        vendor, renderer = random.choice(webgl_vendors)

        stealth(
            driver,
            languages=[random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9"])],
            vendor=vendor,
            platform=platform,
            webgl_vendor=vendor,
            renderer=renderer,
            fix_hairline=True,
            run_on_insecure_origins=True,
        )

        # Randomize fingerprint properties
        driver.execute_script("""
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => Math.floor(Math.random() * 8) + 4
            });
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => Math.floor(Math.random() * 8) + 4
            });
        """)

        return driver
    except Exception:
        if os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)
        raise


def handle_block_retry(driver: webdriver.Chrome, url: str) -> bool:
    """Handle blocking with cookie clearing and CDP header rotation."""
    logger.info("Attempting block evasion for %s", url)
    try:
        driver.delete_all_cookies()
        driver.execute_script("window.localStorage.clear();")
        driver.execute_script("window.sessionStorage.clear();")

        driver.execute_cdp_cmd(
            "Network.setExtraHTTPHeaders",
            {
                "headers": {
                    "Referer": random.choice(
                        ["https://www.google.com/", "https://www.bing.com/"]
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "DNT": "1",
                }
            },
        )

        time.sleep(random.uniform(5, 10))
        driver.get(url)
        return True
    except Exception:
        logger.exception("Block handling failed")
        return False


# ── StreetEasy Scraper ───────────────────────────────────────────────


class StreetEasyScraper(BaseScraper):
    """StreetEasy scraper using Selenium + stealth.

    Ported from ~/Desktop/ApartmentScraper/scrape_streeteasy.py
    """

    def __init__(self, config: SourceConfig | None = None) -> None:
        if config is None:
            config = SourceConfig(
                source=ListingSource.STREETEASY,
                base_url="https://streeteasy.com",
                scrape_interval_hours=6,
                max_pages=10,
                request_delay_range=(3.0, 6.0),
                use_browser=True,
                max_retries=3,
            )
        super().__init__(config)
        self.search_urls = list(DEFAULT_SEARCH_URLS)

    async def scrape(self, borough: str | None = None) -> list[RawListing]:
        """Run full scrape: iterate search URLs × pages, extract cards."""
        all_listings: list[RawListing] = []

        for search_url in self.search_urls:
            for page in range(1, self.config.max_pages + 1):
                self._rate_limit()
                page_listings = self._scrape_page(search_url, page)
                if not page_listings:
                    self.logger.info("No more listings at page %d, moving on", page)
                    break
                all_listings.extend(page_listings)
                self.logger.info(
                    "Page %d: %d listings (total: %d)",
                    page,
                    len(page_listings),
                    len(all_listings),
                )

        return all_listings

    def parse_listing(self, raw: Any) -> RawListing:
        """Parse a single card element (BS4 Tag) into a RawListing."""
        from bs4 import Tag

        if isinstance(raw, Tag):
            return self._parse_card_bs4(raw)
        raise TypeError(f"Expected BS4 Tag, got {type(raw)}")

    def _is_blocked(self, response_or_page: Any) -> bool:
        """Check Selenium driver for block indicators."""
        if isinstance(response_or_page, webdriver.Chrome):
            blocked, _ = _check_blocked(response_or_page)
            return blocked
        return False

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse a search results page HTML into RawListings (for tests/offline)."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        listings: list[RawListing] = []

        for card in soup.select(SEL_LISTING_CARD):
            try:
                listings.append(self.parse_listing(card))
            except Exception:
                self.logger.debug("Failed to parse card", exc_info=True)

        return listings

    # ── Private methods ──────────────────────────────────────────────

    def _scrape_page(self, search_url: str, page_num: int) -> list[RawListing]:
        """Scrape a single search results page with Selenium."""
        cleanup_old_profiles()
        driver = None
        url = f"{search_url}&page={page_num}"

        for attempt in range(1, self.config.max_retries + 1):
            try:
                driver = get_driver()
                driver.get(url)

                blocked, block_type = _check_blocked(driver)
                if blocked:
                    self.logger.warning("Blocked (%s) on attempt %d", block_type, attempt)
                    handle_block_retry(driver, url)

                time.sleep(random.uniform(2, 4))
                cards = driver.find_elements(By.CSS_SELECTOR, SEL_LISTING_CARD)

                if not cards:
                    self.logger.debug("No cards on page %d", page_num)
                    return []

                listings = self._extract_cards_selenium(cards)
                return listings

            except WebDriverException:
                self.logger.warning(
                    "WebDriver error on attempt %d/%d", attempt, self.config.max_retries
                )
                wait = (2**attempt) + random.uniform(0, attempt)
                time.sleep(wait)
            except Exception:
                self.logger.exception(
                    "Unexpected error on page %d attempt %d", page_num, attempt
                )
                break
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass

        return []

    def _extract_cards_selenium(self, cards: list[Any]) -> list[RawListing]:
        """Extract RawListings from Selenium card elements."""
        listings: list[RawListing] = []

        for card in cards:
            try:

                def _text(sel: str) -> str:
                    try:
                        return card.find_element(By.CSS_SELECTOR, sel).text.strip()
                    except NoSuchElementException:
                        return ""

                def _attr(sel: str, attr: str) -> str:
                    try:
                        return (
                            card.find_element(By.CSS_SELECTOR, sel).get_attribute(attr) or ""
                        )
                    except NoSuchElementException:
                        return ""

                address = _text(SEL_ADDRESS)
                detail_url = _attr(SEL_ADDRESS, "href")

                # Beds/baths/sqft from list items
                bbs_items = card.find_elements(
                    By.CSS_SELECTOR, f"{SEL_BEDS_BATHS_SQFT} li"
                )
                beds_raw = (
                    bbs_items[0]
                    .find_element(By.CSS_SELECTOR, SEL_BBS_TEXT)
                    .text.strip()
                    if len(bbs_items) > 0
                    else ""
                )
                baths_raw = (
                    bbs_items[1]
                    .find_element(By.CSS_SELECTOR, SEL_BBS_TEXT)
                    .text.strip()
                    if len(bbs_items) > 1
                    else ""
                )
                sqft_raw = (
                    bbs_items[2]
                    .find_element(By.CSS_SELECTOR, SEL_BBS_TEXT)
                    .text.strip()
                    if len(bbs_items) > 2
                    else ""
                )

                image_url = _attr(f"{SEL_IMAGE}.isActiveImage", "src") or _attr(
                    SEL_IMAGE, "src"
                )

                listings.append(
                    RawListing(
                        source=ListingSource.STREETEASY,
                        source_url=detail_url or f"https://streeteasy.com#{address}",
                        address=address,
                        price=parse_price(_text(SEL_PRICE)),
                        bedrooms=parse_int(beds_raw),
                        bathrooms=parse_float(baths_raw),
                        sqft=parse_int(sqft_raw),
                        images=[image_url] if image_url else [],
                        raw_data={
                            "title": _text(SEL_TITLE),
                            "listed_by": _text(SEL_LISTED_BY),
                            "base_rent_tooltip": _text(SEL_BASE_RENT),
                            "price_tag": _text(SEL_PRICE_TAG),
                        },
                    )
                )
            except Exception:
                self.logger.debug("Failed to extract card", exc_info=True)

        return listings

    @staticmethod
    def _parse_card_bs4(card: Any) -> RawListing:
        """Parse a single card from BeautifulSoup element."""

        def _text(sel: str) -> str:
            el = card.select_one(sel)
            return el.get_text(strip=True) if el else ""

        def _attr(sel: str, attr: str) -> str:
            el = card.select_one(sel)
            return el.get(attr, "") if el else ""

        address = _text(SEL_ADDRESS)
        detail_url = _attr(SEL_ADDRESS, "href")

        bbs_items = card.select(f"{SEL_BEDS_BATHS_SQFT} li")
        beds_raw = (
            bbs_items[0].select_one(SEL_BBS_TEXT).get_text(strip=True)
            if len(bbs_items) > 0 and bbs_items[0].select_one(SEL_BBS_TEXT)
            else ""
        )
        baths_raw = (
            bbs_items[1].select_one(SEL_BBS_TEXT).get_text(strip=True)
            if len(bbs_items) > 1 and bbs_items[1].select_one(SEL_BBS_TEXT)
            else ""
        )
        sqft_raw = (
            bbs_items[2].select_one(SEL_BBS_TEXT).get_text(strip=True)
            if len(bbs_items) > 2 and bbs_items[2].select_one(SEL_BBS_TEXT)
            else ""
        )

        img = card.select_one(f"{SEL_IMAGE}.isActiveImage") or card.select_one(SEL_IMAGE)
        image_url = img.get("src", "") if img else ""

        return RawListing(
            source=ListingSource.STREETEASY,
            source_url=detail_url or f"https://streeteasy.com#{address}",
            address=address,
            price=parse_price(_text(SEL_PRICE)),
            bedrooms=parse_int(beds_raw),
            bathrooms=parse_float(baths_raw),
            sqft=parse_int(sqft_raw),
            images=[image_url] if image_url else [],
            raw_data={
                "title": _text(SEL_TITLE),
                "listed_by": _text(SEL_LISTED_BY),
            },
        )


# Register with the task system
register_scraper(ListingSource.STREETEASY, StreetEasyScraper)
