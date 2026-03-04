"""Zumper scraper — extracts listing data from JSON-LD structured data."""

from __future__ import annotations

import json
import logging
import random
from typing import Any

import requests
from bs4 import BeautifulSoup

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import (
    BaseScraper,
    RawListing,
    SourceConfig,
    parse_float,
    parse_int,
)
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
                scrape_interval_hours=8,
                max_pages=10,
                request_delay_range=(3.0, 5.0),
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

    async def scrape(self, borough: str | None = None) -> list[RawListing]:
        """Scrape Zumper search pages."""
        all_listings: list[RawListing] = []

        for page in range(1, self.config.max_pages + 1):
            self._rate_limit()
            url = (
                f"{self.config.base_url}?page={page}"
                if page > 1
                else self.config.base_url
            )
            try:
                resp = self._session.get(url, timeout=20)
                resp.raise_for_status()
            except requests.RequestException:
                self.logger.exception("Failed to fetch Zumper page %d", page)
                break

            page_listings = self.parse_listing_page(resp.text)
            if not page_listings:
                break
            all_listings.extend(page_listings)
            self.logger.info(
                "Page %d: %d listings (total %d)",
                page,
                len(page_listings),
                len(all_listings),
            )

        return all_listings

    def parse_listing(self, raw: Any) -> RawListing:
        """Parse a single JSON-LD dict into a RawListing."""
        if not isinstance(raw, dict):
            raise TypeError(f"Expected dict, got {type(raw)}")
        result = self._parse_ld_item(raw)
        if result is None:
            raise ValueError("Could not parse JSON-LD item (no address)")
        return result

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse listings from JSON-LD embedded in page HTML (for tests/offline)."""
        ld_blocks = extract_json_ld(html)
        listings: list[RawListing] = []

        for block in ld_blocks:
            if block.get("@type") == "ItemList":
                for item in block.get("itemListElement", []):
                    actual = item.get("item", item)
                    try:
                        listing = self._parse_ld_item(actual)
                        if listing:
                            listings.append(listing)
                    except Exception:
                        self.logger.debug("Failed to parse ItemList entry", exc_info=True)

            elif block.get("@type") in (
                "Apartment",
                "Residence",
                "SingleFamilyResidence",
                "House",
            ):
                try:
                    listing = self._parse_ld_item(block)
                    if listing:
                        listings.append(listing)
                except Exception:
                    self.logger.debug("Failed to parse LD item", exc_info=True)

        return listings

    def _parse_ld_item(self, item: dict[str, Any]) -> RawListing | None:
        """Parse a single JSON-LD Apartment/Residence item."""
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
        price: int | None = None
        offers = item.get("offers", {})
        if isinstance(offers, dict):
            price = parse_int(offers.get("price", offers.get("lowPrice")))
        elif isinstance(offers, list) and offers:
            price = parse_int(offers[0].get("price"))

        beds = parse_int(item.get("numberOfBedrooms", item.get("numberOfRooms")))
        baths = parse_float(
            item.get("numberOfBathroomsTotal", item.get("numberOfBathrooms"))
        )

        # Sqft
        floor_size = item.get("floorSize", {})
        sqft: int | None = None
        if isinstance(floor_size, dict):
            sqft = parse_int(floor_size.get("value"))
        elif floor_size:
            sqft = parse_int(floor_size)

        # Images
        images_raw = item.get("image", item.get("photo", []))
        if isinstance(images_raw, str):
            images = [images_raw]
        elif isinstance(images_raw, list):
            images = [
                img.get("contentUrl", img.get("url", img))
                if isinstance(img, dict)
                else str(img)
                for img in images_raw[:5]
            ]
        else:
            images = []

        url = item.get("url", "")
        if url and not url.startswith("http"):
            url = f"https://www.zumper.com{url}"

        geo = item.get("geo", {})

        return RawListing(
            source=ListingSource.ZUMPER,
            source_url=url,
            address=address,
            price=price,
            bedrooms=beds,
            bathrooms=baths,
            sqft=sqft,
            description=item.get("description"),
            images=images,
            raw_data={
                "name": item.get("name", ""),
                "lat": geo.get("latitude") if isinstance(geo, dict) else None,
                "lng": geo.get("longitude") if isinstance(geo, dict) else None,
            },
        )


register_scraper(ListingSource.ZUMPER, ZumperScraper)
