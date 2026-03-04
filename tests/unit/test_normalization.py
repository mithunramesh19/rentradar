"""Tests for normalization pipeline."""

import pytest

from rentradar_workers.normalization.pipeline import (
    NormalizedListing,
    canonical_hash,
    clean_address,
    normalize,
    parse_bathrooms,
    parse_bedrooms,
    parse_price,
    parse_sqft,
)


class TestCleanAddress:
    def test_strips_apartment(self):
        assert clean_address("123 Main Street Apt 4B") == "123 Main St"

    def test_strips_unit(self):
        assert clean_address("456 Broadway, Unit 12") == "456 Broadway"

    def test_strips_suite(self):
        assert clean_address("789 5th Ave Suite 100") == "789 5th Ave"

    def test_normalizes_street_type(self):
        assert clean_address("100 Park Avenue") == "100 Park Ave"

    def test_normalizes_boulevard(self):
        assert clean_address("200 Ocean Boulevard") == "200 Ocean Blvd"

    def test_collapses_whitespace(self):
        assert clean_address("123   Main    Street") == "123 Main St"

    def test_title_case(self):
        assert clean_address("123 main street") == "123 Main St"

    def test_empty_string(self):
        assert clean_address("") == ""

    def test_ordinal_preserved(self):
        result = clean_address("123 East 45th Street")
        assert "45th" in result

    def test_strip_floor(self):
        assert clean_address("100 Broadway Floor 3") == "100 Broadway"

    def test_full_address(self):
        result = clean_address("350 West 42nd Street, Apt 5A")
        assert result == "350 West 42nd St"


class TestParsePrice:
    def test_basic_price(self):
        assert parse_price("$2,500") == 250000

    def test_price_with_decimals(self):
        assert parse_price("$1,234.56") == 123456

    def test_no_dollar_sign(self):
        assert parse_price("3000") == 300000

    def test_empty(self):
        assert parse_price("") is None

    def test_no_match(self):
        assert parse_price("call for pricing") is None

    def test_price_with_text(self):
        assert parse_price("$2,500/month") == 250000


class TestParseBedrooms:
    def test_studio(self):
        assert parse_bedrooms("Studio") == 0.0

    def test_numeric_beds(self):
        assert parse_bedrooms("2 Bedrooms") == 2.0

    def test_abbreviation(self):
        assert parse_bedrooms("3br") == 3.0

    def test_bare_number(self):
        assert parse_bedrooms("1") == 1.0

    def test_empty(self):
        assert parse_bedrooms("") is None

    def test_studio_mixed_case(self):
        assert parse_bedrooms("STUDIO") == 0.0


class TestParseBathrooms:
    def test_basic(self):
        assert parse_bathrooms("1 Bathroom") == 1.0

    def test_half_bath(self):
        assert parse_bathrooms("1.5 baths") == 1.5

    def test_bare_number(self):
        assert parse_bathrooms("2") == 2.0

    def test_empty(self):
        assert parse_bathrooms("") is None


class TestParseSqft:
    def test_basic(self):
        assert parse_sqft("1,200 sq ft") == 1200

    def test_no_comma(self):
        assert parse_sqft("800 sqft") == 800

    def test_bare_number(self):
        assert parse_sqft("950") == 950

    def test_empty(self):
        assert parse_sqft("") is None

    def test_sf_abbreviation(self):
        assert parse_sqft("1100 SF") == 1100


class TestCanonicalHash:
    def test_same_input_same_hash(self):
        h1 = canonical_hash("streeteasy", "123 Main St", 2.0)
        h2 = canonical_hash("streeteasy", "123 Main St", 2.0)
        assert h1 == h2

    def test_different_source_different_hash(self):
        h1 = canonical_hash("streeteasy", "123 Main St", 2.0)
        h2 = canonical_hash("craigslist", "123 Main St", 2.0)
        assert h1 != h2

    def test_different_beds_different_hash(self):
        h1 = canonical_hash("streeteasy", "123 Main St", 1.0)
        h2 = canonical_hash("streeteasy", "123 Main St", 2.0)
        assert h1 != h2

    def test_none_bedrooms(self):
        h = canonical_hash("streeteasy", "123 Main St", None)
        assert len(h) == 64  # SHA-256 hex length


class TestNormalize:
    def test_full_pipeline(self):
        result = normalize(
            source="streeteasy",
            address="350 West 42nd Street, Apt 5A",
            price="$3,200/month",
            bedrooms="2 Bedrooms",
            bathrooms="1 Bath",
            sqft="900 sq ft",
        )
        assert isinstance(result, NormalizedListing)
        assert result.address_clean == "350 West 42nd St"
        assert result.price_cents == 320000
        assert result.bedrooms == 2.0
        assert result.bathrooms == 1.0
        assert result.sqft == 900
        assert len(result.canonical_hash) == 64

    def test_extra_fields_passed_through(self):
        result = normalize(
            source="craigslist",
            address="100 Broadway",
            price="$1,500",
            bedrooms="studio",
            bathrooms="1",
            sqft="",
            neighborhood="East Village",
        )
        assert result.extra == {"neighborhood": "East Village"}
        assert result.bedrooms == 0.0
        assert result.sqft is None
