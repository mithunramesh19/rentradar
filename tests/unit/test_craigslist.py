"""Tests for Craigslist scraper."""

from pathlib import Path

import pytest

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.craigslist import CraigslistScraper

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def scraper():
    return CraigslistScraper()


@pytest.fixture
def search_html():
    return (FIXTURES / "craigslist_search.html").read_text()


class TestParseListingPage:
    def test_parses_three_results(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        assert len(listings) == 3

    def test_first_listing(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        first = listings[0]
        assert first.source == ListingSource.CRAIGSLIST
        assert first.address == "Renovated 1BR near Prospect Park"
        assert first.price == 2400
        assert "1001.html" in first.source_url

    def test_relative_urls_resolved(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        for listing in listings:
            assert listing.source_url.startswith("https://")

    def test_third_listing(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        third = listings[2]
        assert third.address == "Cozy Studio near Subway"
        assert third.price == 1750

    def test_price_stored_as_int(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        for listing in listings:
            assert isinstance(listing.price, int)
