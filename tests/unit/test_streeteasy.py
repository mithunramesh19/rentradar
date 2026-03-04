"""Tests for StreetEasy scraper — parse_listing_page with HTML fixture."""

from pathlib import Path

import pytest

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.streeteasy import StreetEasyScraper

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def scraper():
    return StreetEasyScraper()


@pytest.fixture
def search_html():
    return (FIXTURES / "streeteasy_search.html").read_text()


class TestParseListingPage:
    def test_parses_two_cards(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        assert len(listings) == 2

    def test_first_listing_fields(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        first = listings[0]
        assert first.source == ListingSource.STREETEASY
        assert first.address == "350 West 26th Street #4A"
        assert first.price == 3200
        assert first.bedrooms == 2
        assert first.bathrooms == 1.0
        assert first.sqft == 850
        assert first.source_url == "https://streeteasy.com/rental/1234567"
        assert "photo1.jpg" in first.images[0]

    def test_second_listing_studio(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        second = listings[1]
        assert second.address == "88 East 10th Street #2B"
        assert second.price == 2100
        assert second.bedrooms == 0  # "Studio" → 0
        assert second.sqft is None  # No sqft in fixture

    def test_raw_data_has_title(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        assert listings[0].raw_data["title"] == "Spacious 2BR in Chelsea"
        assert listings[1].raw_data["title"] == "Sunny Studio in East Village"

    def test_canonical_key_unique(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        keys = {listing.canonical_key for listing in listings}
        assert len(keys) == 2


class TestScraperConfig:
    def test_default_config(self, scraper):
        assert scraper.config.source == ListingSource.STREETEASY
        assert scraper.config.base_url == "https://streeteasy.com"
        assert scraper.config.use_browser is True
        assert scraper.config.request_delay_range == (3.0, 6.0)
