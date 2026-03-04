"""Tests for base scraper parse helpers and models."""

import pytest

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import (
    RawListing,
    SourceConfig,
    parse_float,
    parse_int,
    parse_price,
)


class TestParsePrice:
    def test_dollar_sign(self):
        assert parse_price("$3,200") == 3200

    def test_with_suffix(self):
        assert parse_price("$4,500/mo") == 4500

    def test_no_dollar(self):
        assert parse_price("2800") == 2800

    def test_empty(self):
        assert parse_price("") is None

    def test_no_digits(self):
        assert parse_price("call for pricing") is None


class TestParseInt:
    def test_with_text(self):
        assert parse_int("2 bed") == 2

    def test_studio(self):
        assert parse_int("Studio") == 0

    def test_bare_number(self):
        assert parse_int("3") == 3

    def test_empty(self):
        assert parse_int("") is None

    def test_none(self):
        assert parse_int(None) is None

    def test_int_passthrough(self):
        assert parse_int(5) == 5

    def test_sqft_text(self):
        assert parse_int("1,100 sqft") == 1

    def test_float_input(self):
        assert parse_int(2.5) == 2


class TestParseFloat:
    def test_with_text(self):
        assert parse_float("1.5 baths") == 1.5

    def test_integer(self):
        assert parse_float("2") == 2.0

    def test_empty(self):
        assert parse_float("") is None

    def test_none(self):
        assert parse_float(None) is None

    def test_float_passthrough(self):
        assert parse_float(1.5) == 1.5


class TestRawListing:
    def test_canonical_key_deterministic(self):
        a = RawListing(source=ListingSource.STREETEASY, source_url="https://example.com/1")
        b = RawListing(source=ListingSource.STREETEASY, source_url="https://example.com/1")
        assert a.canonical_key == b.canonical_key

    def test_canonical_key_differs_by_source(self):
        a = RawListing(source=ListingSource.STREETEASY, source_url="https://example.com/1")
        b = RawListing(source=ListingSource.CRAIGSLIST, source_url="https://example.com/1")
        assert a.canonical_key != b.canonical_key

    def test_typed_fields(self):
        listing = RawListing(
            source=ListingSource.ZILLOW,
            source_url="https://example.com",
            price=3000,
            bedrooms=2,
            bathrooms=1.5,
            sqft=900,
        )
        assert listing.price == 3000
        assert listing.bedrooms == 2
        assert listing.bathrooms == 1.5
        assert listing.sqft == 900


class TestSourceConfig:
    def test_defaults(self):
        config = SourceConfig(source=ListingSource.STREETEASY, base_url="https://example.com")
        assert config.max_pages == 50
        assert config.request_delay_range == (2.0, 5.0)
        assert config.use_browser is False
        assert config.max_retries == 3
        assert config.scrape_interval_hours == 6
