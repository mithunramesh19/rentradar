"""Unit tests for permit tracking modules."""

from datetime import datetime

import pytest


class TestATTOMClient:
    def test_client_no_key(self):
        from rentradar_workers.permits.attom_client import ATTOMClient

        client = ATTOMClient(api_key="")
        assert client.has_attom_key is False

    def test_client_with_key(self):
        from rentradar_workers.permits.attom_client import ATTOMClient

        client = ATTOMClient(api_key="test-key-123")
        assert client.has_attom_key is True

    def test_parse_nyc_permit(self):
        from rentradar_workers.permits.attom_client import ATTOMClient

        client = ATTOMClient()
        row = {
            "job__": "123456789",
            "house__": "100",
            "street_name": "BROADWAY",
            "borough": "1",
            "permit_type": "NB",
            "residential": "50",
            "estimated_job_cost": "5000000",
            "filing_date": "2024-01-15T00:00:00.000",
            "issuance_date": "2024-03-01T00:00:00.000",
            "filing_status": "APPROVED",
            "gis_latitude": "40.7128",
            "gis_longitude": "-74.0060",
        }
        permit = client._parse_nyc_permit(row)

        assert permit.permit_number == "123456789"
        assert permit.address == "100 BROADWAY"
        assert permit.borough == "Manhattan"
        assert permit.permit_type == "NB"
        assert permit.residential_units == 50
        assert permit.estimated_cost == 5000000
        assert permit.filing_date == datetime(2024, 1, 15)
        assert permit.latitude == pytest.approx(40.7128)
        assert permit.longitude == pytest.approx(-74.006)


class TestHelpers:
    def test_borough_from_code(self):
        from rentradar_workers.permits.attom_client import _borough_from_code

        assert _borough_from_code("1") == "Manhattan"
        assert _borough_from_code("2") == "Bronx"
        assert _borough_from_code("3") == "Brooklyn"
        assert _borough_from_code("4") == "Queens"
        assert _borough_from_code("5") == "Staten Island"

    def test_borough_from_county(self):
        from rentradar_workers.permits.attom_client import _borough_from_county

        assert _borough_from_county("NEW YORK") == "Manhattan"
        assert _borough_from_county("KINGS") == "Brooklyn"

    def test_nyc_borough_code(self):
        from rentradar_workers.permits.attom_client import _nyc_borough_code

        assert _nyc_borough_code("Manhattan") == "1"
        assert _nyc_borough_code("Brooklyn") == "3"

    def test_sanitize(self):
        from rentradar_workers.permits.attom_client import _sanitize

        assert _sanitize("O'Brien") == "O''Brien"
        assert _sanitize("100%") == "100"
        assert _sanitize("test_value") == "testvalue"

    def test_safe_int(self):
        from rentradar_workers.permits.attom_client import _safe_int

        assert _safe_int("123") == 123
        assert _safe_int("123.45") == 123
        assert _safe_int(None) is None
        assert _safe_int("not_a_number") is None

    def test_parse_date(self):
        from rentradar_workers.permits.attom_client import _parse_date

        assert _parse_date("2024-01-15") == datetime(2024, 1, 15)
        assert _parse_date("2024-01-15T10:30:00") == datetime(2024, 1, 15, 10, 30)
        assert _parse_date("01/15/2024") == datetime(2024, 1, 15)
        assert _parse_date(None) is None
        assert _parse_date("not-a-date") is None


class TestTracker:
    def test_haversine_same_point(self):
        from rentradar_workers.permits.tracker import _haversine_miles

        dist = _haversine_miles(40.7128, -74.006, 40.7128, -74.006)
        assert dist == 0.0

    def test_haversine_known_distance(self):
        from rentradar_workers.permits.tracker import _haversine_miles

        # Times Square to Empire State Building ≈ 0.5 miles
        dist = _haversine_miles(40.7580, -73.9855, 40.7484, -73.9857)
        assert 0.5 < dist < 1.0

    def test_haversine_manhattan_to_brooklyn(self):
        from rentradar_workers.permits.tracker import _haversine_miles

        # Manhattan (midtown) to Brooklyn (downtown) ≈ 5-7 miles
        dist = _haversine_miles(40.7580, -73.9855, 40.6892, -73.9857)
        assert 4.0 < dist < 6.0
