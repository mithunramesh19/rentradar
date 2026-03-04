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
        assert first.title == "Renovated 1BR near Prospect Park"
        assert first.price == "$2,400"
        assert "1001.html" in first.source_url

    def test_relative_urls_resolved(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        for listing in listings:
            assert listing.source_url.startswith("https://")

    def test_third_listing_studio(self, scraper, search_html):
        listings = scraper.parse_listing_page(search_html)
        third = listings[2]
        assert third.title == "Cozy Studio near Subway"
        assert third.price == "$1,750"


class TestParseDetail:
    def test_parse_detail_page(self, scraper):
        html = """
        <html><body>
        <span id="titletextonly">Beautiful 2BR in Park Slope</span>
        <span class="price">$2,800</span>
        <section id="postingbody">Spacious apartment with great light</section>
        <div id="map" data-latitude="40.6745" data-longitude="-73.9780"></div>
        <p class="attrgroup"><span>2BR / 1Ba</span></p>
        <p class="attrgroup"><span>900ft2</span></p>
        </body></html>
        """
        result = scraper.parse_listing_detail(html, "https://newyork.craigslist.org/apt/1234")
        assert result.title == "Beautiful 2BR in Park Slope"
        assert result.price == "$2,800"
        assert result.description == "Spacious apartment with great light"
        assert result.detail_data["lat"] == "40.6745"
