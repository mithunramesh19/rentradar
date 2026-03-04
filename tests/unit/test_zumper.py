"""Tests for Zumper scraper."""

from pathlib import Path

import pytest

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.zumper import ZumperScraper, extract_json_ld

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def scraper():
    return ZumperScraper()


@pytest.fixture
def search_html():
    return (FIXTURES / "zumper_search.html").read_text()


class TestExtractJsonLd:
    def test_extracts_item_list(self, search_html):
        blocks = extract_json_ld(search_html)
        assert len(blocks) == 1
        assert blocks[0]["@type"] == "ItemList"

    def test_empty_html(self):
        assert extract_json_ld("<html></html>") == []

    def test_invalid_json(self):
        html = '<script type="application/ld+json">{invalid}</script>'
        assert extract_json_ld(html) == []


class TestParseListingPage:
    def test_parses_two_listings(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        assert len(listings) == 2

    def test_first_listing(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        first = listings[0]
        assert first.source == ListingSource.ZUMPER
        assert first.title == "Modern 1BR in Williamsburg"
        assert "150 North 4th Street" in first.address
        assert "$2900" in first.price
        assert first.bedrooms == "1"
        assert first.bathrooms == "1"
        assert first.sqft == "650"
        assert len(first.image_urls) == 2
        assert first.detail_data["lat"] == 40.7178

    def test_relative_url_resolved(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        first = listings[0]
        assert first.source_url.startswith("https://www.zumper.com")

    def test_second_listing_studio(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        second = listings[1]
        assert second.title == "Spacious Studio in Harlem"
        assert second.bedrooms == "0"
        assert "$1800" in second.price

    def test_single_image_string(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        second = listings[1]
        assert len(second.image_urls) == 1
        assert "b1.jpg" in second.image_urls[0]
