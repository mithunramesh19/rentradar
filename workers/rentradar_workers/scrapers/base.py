"""Base scraper ABC, configuration, and raw listing model."""

from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rentradar_common.constants import ListingSource

logger = logging.getLogger(__name__)

# ── Parse helpers (raw strings → typed values) ───────────────────────

_PRICE_RE = re.compile(r"[\$]?\s*([\d,]+)")
_INT_RE = re.compile(r"([\d,]+)")
_FLOAT_RE = re.compile(r"([\d.]+)")


def parse_price(raw: str) -> int | None:
    """'$3,200/month' → 3200.  Returns dollars as int, or None."""
    if not raw:
        return None
    m = _PRICE_RE.search(raw)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_int(raw: str | int | float | None) -> int | None:
    """'2 bed' → 2, 'Studio' → 0, '' → None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    s = str(raw).strip()
    if not s:
        return None
    if re.search(r"\bstudio\b", s, re.IGNORECASE):
        return 0
    m = _INT_RE.search(s)
    return int(m.group(1).replace(",", "")) if m else None


def parse_float(raw: str | int | float | None) -> float | None:
    """'1.5 baths' → 1.5, '' → None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    m = _FLOAT_RE.search(s)
    return float(m.group(1)) if m else None


class SourceConfig(BaseModel):
    """Configuration for a scraper source."""

    source: ListingSource
    base_url: str
    scrape_interval_hours: int = 6
    max_pages: int = 50
    request_delay_range: tuple[float, float] = (2.0, 5.0)
    use_browser: bool = False
    max_retries: int = 3


class RawListing(BaseModel):
    """Raw listing data as scraped — before normalization."""

    source: ListingSource
    source_url: str
    source_listing_id: str | None = None
    address: str = ""
    unit: str | None = None
    price: int | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    amenities: list[str] = Field(default_factory=list)
    description: str | None = None
    images: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    @property
    def canonical_key(self) -> str:
        """Deterministic key for dedup: hash of source + source_url."""
        payload = f"{self.source}:{self.source_url}"
        return hashlib.sha256(payload.encode()).hexdigest()


class BlockedError(Exception):
    """Raised when a scraper detects it is being blocked."""


class BaseScraper(ABC):
    """Abstract base class for all RentRadar scrapers."""

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(f"scraper.{config.source}")

    @abstractmethod
    async def scrape(self, borough: str | None = None) -> list[RawListing]:
        """Run the full scrape cycle. Returns raw listings."""
        ...

    @abstractmethod
    def parse_listing(self, raw: Any) -> RawListing:
        """Parse a single raw element (HTML element, JSON dict, etc.) into a RawListing."""
        ...

    def _rate_limit(self) -> None:
        """Random sleep within the configured delay range."""
        lo, hi = self.config.request_delay_range
        delay = random.uniform(lo, hi)
        time.sleep(delay)

    def _is_blocked(self, response_or_page: Any) -> bool:
        """Check if the response indicates blocking. Override in subclass."""
        return False

    def _retry_on_block(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Call *func* with tenacity retry on BlockedError."""

        @retry(
            retry=retry_if_exception_type(BlockedError),
            stop=stop_after_attempt(self.config.max_retries),
            wait=wait_exponential(multiplier=2, min=4, max=30),
            reraise=True,
        )
        def _inner() -> Any:
            result = func(*args, **kwargs)
            if self._is_blocked(result):
                raise BlockedError(f"{self.config.source}: blocked, retrying")
            return result

        return _inner()

    async def scrape_with_metrics(self, borough: str | None = None) -> list[RawListing]:
        """Run scrape() and log metrics."""
        source = self.config.source
        self.logger.info("Starting scrape for %s", source)
        start = time.monotonic()
        try:
            listings = await self.scrape(borough)
            duration = time.monotonic() - start
            self.logger.info(
                "Scraped %d listings from %s in %.1fs", len(listings), source, duration
            )
            return listings
        except Exception:
            duration = time.monotonic() - start
            self.logger.exception("Scrape failed for %s after %.1fs", source, duration)
            raise
