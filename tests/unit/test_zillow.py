"""Tests for Zillow scraper."""

from pathlib import Path

import pytest

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.zillow import ZillowScraper

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def scraper():
    return ZillowScraper()


@pytest.fixture
def search_html():
    return (FIXTURES / "zillow_search.html").read_text()


class TestParseListingPage:
    def test_parses_two_cards(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        assert len(listings) == 2

    def test_first_listing(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        first = listings[0]
        assert first.source == ListingSource.ZILLOW
        assert first.address == "200 East 82nd Street, New York, NY"
        assert first.price == 4500
        assert first.bedrooms == 2
        assert first.bathrooms == 2.0
        assert first.sqft == 1100
        assert "z1.jpg" in first.images[0]

    def test_urls_fully_qualified(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        for listing in listings:
            assert listing.source_url.startswith("https://")

    def test_config_uses_browser(self, scraper):
        assert scraper.config.use_browser is True
