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
        assert first.price == "$3,200"
        assert first.bedrooms == "2 bed"
        assert first.bathrooms == "1 bath"
        assert first.sqft == "850 ft²"
        assert first.listed_by == "Listed by Compass"
        assert first.source_url == "https://streeteasy.com/rental/1234567"
        assert "photo1.jpg" in first.image_urls[0]

    def test_second_listing_studio(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        second = listings[1]
        assert second.address == "88 East 10th Street #2B"
        assert second.price == "$2,100"
        assert second.bedrooms == "Studio"
        assert second.sqft == ""  # No sqft in fixture

    def test_title_extracted(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        assert listings[0].title == "Spacious 2BR in Chelsea"
        assert listings[1].title == "Sunny Studio in East Village"

    def test_canonical_key_unique(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        keys = {l.canonical_key for l in listings}
        assert len(keys) == 2


class TestScraperConfig:
    def test_default_config(self, scraper):
        assert scraper.config.source == ListingSource.STREETEASY
        assert scraper.config.base_url == "https://streeteasy.com"
        assert scraper.config.rate_limit_seconds == 3.0
