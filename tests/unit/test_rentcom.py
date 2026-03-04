"""Tests for Rent.com scraper."""

from pathlib import Path

import pytest

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.rentcom import RentComScraper, extract_next_data

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def scraper():
    return RentComScraper()


@pytest.fixture
def search_html():
    return (FIXTURES / "rentcom_search.html").read_text()


class TestExtractNextData:
    def test_extracts_json(self, search_html):
        data = extract_next_data(search_html)
        assert "props" in data
        assert "pageProps" in data["props"]

    def test_empty_html(self):
        assert extract_next_data("<html></html>") == {}

    def test_invalid_json(self):
        html = '<script id="__NEXT_DATA__" type="application/json">{invalid}</script>'
        assert extract_next_data(html) == {}


class TestParseListingPage:
    def test_parses_two_listings(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        assert len(listings) == 2

    def test_first_listing_rent_range(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        first = listings[0]
        assert first.source == ListingSource.RENTCOM
        assert first.title == "The Beacon"
        assert "2800" in first.price
        assert first.bedrooms == "1"
        assert first.neighborhood == "Newport"

    def test_relative_url_resolved(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        first = listings[0]
        assert first.source_url.startswith("https://www.rent.com")

    def test_second_listing_scalar_rent(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        second = listings[1]
        assert "3500" in second.price
        assert second.bedrooms == "2"

    def test_images_extracted(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        first = listings[0]
        assert len(first.image_urls) == 2
        assert "photo1.jpg" in first.image_urls[0]
