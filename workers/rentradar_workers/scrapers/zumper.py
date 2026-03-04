"""Zumper scraper — extracts listing data from JSON-LD structured data."""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import BaseScraper, RawListing, SourceConfig
from rentradar_workers.scrapers.tasks import register_scraper

logger = logging.getLogger(__name__)

ZUMPER_URL = "https://www.zumper.com/apartments-for-rent/new-york-ny"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
]


def extract_json_ld(html: str) -> list[dict[str, Any]]:
    """Extract all JSON-LD blocks from page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []

    for script in soup.select('script[type="application/ld+json"]'):
        text = script.string
        if not text:
            continue
        try:
            data = json.loads(text)
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
        except json.JSONDecodeError:
            logger.debug("Failed to parse JSON-LD block", exc_info=True)

    return results


class ZumperScraper(BaseScraper):
    """Zumper scraper using JSON-LD structured data."""

    def __init__(self, config: SourceConfig | None = None) -> None:
        if config is None:
            config = SourceConfig(
                source=ListingSource.ZUMPER,
                base_url=ZUMPER_URL,
                rate_limit_seconds=3.0,
                max_pages=10,
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
        """Scrape Zumper search pages."""
        all_listings: list[RawListing] = []

        for page in range(1, self.config.max_pages + 1):
            self.throttle()
            url = f"{self.config.base_url}?page={page}" if page > 1 else self.config.base_url
            try:
                resp = self._session.get(url, timeout=self.config.timeout_seconds)
                resp.raise_for_status()
            except requests.RequestException:
                self.logger.exception("Failed to fetch Zumper page %d", page)
                break

            page_listings = self.parse_listing_page(resp.text)
            if not page_listings:
                break
            all_listings.extend(page_listings)
            self.logger.info(
                "Page %d: %d listings (total %d)", page, len(page_listings), len(all_listings)
            )

        return all_listings

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse listings from JSON-LD embedded in page HTML."""
        ld_blocks = extract_json_ld(html)
        listings: list[RawListing] = []

        for block in ld_blocks:
            # Handle ItemList with individual listings
            if block.get("@type") == "ItemList":
                for item in block.get("itemListElement", []):
                    actual = item.get("item", item)
                    try:
                        listing = self._parse_ld_item(actual)
                        if listing:
                            listings.append(listing)
                    except Exception:
                        self.logger.debug("Failed to parse ItemList entry", exc_info=True)

            # Handle individual Apartment/Residence entries
            elif block.get("@type") in ("Apartment", "Residence", "SingleFamilyResidence", "House"):
                try:
                    listing = self._parse_ld_item(block)
                    if listing:
                        listings.append(listing)
                except Exception:
                    self.logger.debug("Failed to parse LD item", exc_info=True)

        return listings

    def parse_listing_detail(self, html: str, url: str) -> RawListing:
        """Parse detail page from JSON-LD."""
        ld_blocks = extract_json_ld(html)

        for block in ld_blocks:
            if block.get("@type") in ("Apartment", "Residence", "SingleFamilyResidence"):
                listing = self._parse_ld_item(block)
                if listing:
                    listing.source_url = url
                    return listing

        return RawListing(source=ListingSource.ZUMPER, source_url=url)

    def _parse_ld_item(self, item: dict[str, Any]) -> RawListing | None:
        """Parse a single JSON-LD Apartment/Residence item."""
        # Address from structured address object or string
        address_obj = item.get("address", {})
        if isinstance(address_obj, dict):
            parts = [
                address_obj.get("streetAddress", ""),
                address_obj.get("addressLocality", ""),
                address_obj.get("addressRegion", ""),
            ]
            address = ", ".join(p for p in parts if p)
        else:
            address = str(address_obj)

        if not address:
            return None

        # Price from offers
        price = ""
        offers = item.get("offers", {})
        if isinstance(offers, dict):
            price_val = offers.get("price", offers.get("lowPrice", ""))
            currency = offers.get("priceCurrency", "USD")
            if price_val:
                price = f"${price_val}" if currency == "USD" else f"{price_val} {currency}"
        elif isinstance(offers, list) and offers:
            price_val = offers[0].get("price", "")
            if price_val:
                price = f"${price_val}"

        # Beds/baths
        beds = str(item.get("numberOfBedrooms", item.get("numberOfRooms", "")))
        baths = str(item.get("numberOfBathroomsTotal", item.get("numberOfBathrooms", "")))

        # Sqft
        floor_size = item.get("floorSize", {})
        sqft = ""
        if isinstance(floor_size, dict):
            sqft = str(floor_size.get("value", ""))
        elif floor_size:
            sqft = str(floor_size)

        # Images
        images = item.get("image", item.get("photo", []))
        if isinstance(images, str):
            images = [images]
        elif isinstance(images, list):
            images = [
                img.get("contentUrl", img.get("url", img)) if isinstance(img, dict) else str(img)
                for img in images[:5]
            ]

        url = item.get("url", "")
        if url and not url.startswith("http"):
            url = f"https://www.zumper.com{url}"

        return RawListing(
            source=ListingSource.ZUMPER,
            source_url=url,
            title=item.get("name", ""),
            address=address,
            price=price,
            bedrooms=beds if beds != "None" and beds else "",
            bathrooms=baths if baths != "None" and baths else "",
            sqft=sqft if sqft != "None" and sqft else "",
            description=item.get("description", ""),
            image_urls=images,
            detail_data={
                "lat": item.get("geo", {}).get("latitude") if isinstance(item.get("geo"), dict) else None,
                "lng": item.get("geo", {}).get("longitude") if isinstance(item.get("geo"), dict) else None,
            },
        )


register_scraper(ListingSource.ZUMPER, ZumperScraper)
