"""Base scraper ABC, configuration, and raw listing model."""

from __future__ import annotations

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from rentradar_common.constants import ListingSource

logger = logging.getLogger(__name__)


class SourceConfig(BaseModel):
    """Configuration for a scraper source."""

    source: ListingSource
    base_url: str
    rate_limit_seconds: float = 2.0
    max_pages: int = 50
    timeout_seconds: int = 30
    max_retries: int = 3
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class RawListing(BaseModel):
    """Raw listing data as scraped — before normalization."""

    source: ListingSource
    source_url: str
    source_id: str = ""
    title: str = ""
    address: str = ""
    price: str = ""
    bedrooms: str = ""
    bathrooms: str = ""
    sqft: str = ""
    description: str = ""
    neighborhood: str = ""
    borough: str = ""
    listed_by: str = ""
    image_urls: list[str] = Field(default_factory=list)
    amenities: list[str] = Field(default_factory=list)
    detail_data: dict[str, Any] = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_html: str = ""

    @property
    def canonical_key(self) -> str:
        """Deterministic key for dedup: hash of source + source_url."""
        payload = f"{self.source}:{self.source_url}"
        return hashlib.sha256(payload.encode()).hexdigest()


class BaseScraper(ABC):
    """Abstract base class for all RentRadar scrapers."""

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(f"scraper.{config.source}")
        self._last_request_time: float = 0.0

    @abstractmethod
    def scrape(self) -> list[RawListing]:
        """Run the full scrape cycle. Returns raw listings."""
        ...

    @abstractmethod
    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse a search results page into raw listings."""
        ...

    @abstractmethod
    def parse_listing_detail(self, html: str, url: str) -> RawListing:
        """Parse a single listing detail page."""
        ...

    def throttle(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.monotonic() - self._last_request_time
        wait = self.config.rate_limit_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    def scrape_with_metrics(self) -> list[RawListing]:
        """Run scrape() and log metrics."""
        source = self.config.source
        self.logger.info("Starting scrape for %s", source)
        start = time.monotonic()
        try:
            listings = self.scrape()
            duration = time.monotonic() - start
            self.logger.info(
                "Scraped %d listings from %s in %.1fs", len(listings), source, duration
            )
            return listings
        except Exception:
            duration = time.monotonic() - start
            self.logger.exception("Scrape failed for %s after %.1fs", source, duration)
            raise
