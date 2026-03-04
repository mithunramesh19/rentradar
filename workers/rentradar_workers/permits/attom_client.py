"""ATTOM Data API client for building permits, with NYC Open Data fallback.

ATTOM: https://api.gateway.attomdata.com/propertyapi/v1.0.0/
NYC Open Data DOB Permits: https://data.cityofnewyork.us/resource/ipu4-2vj7.json
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

ATTOM_BASE_URL = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"
NYC_OPEN_DATA_URL = "https://data.cityofnewyork.us/resource/ipu4-2vj7.json"


@dataclass
class PermitRecord:
    """Normalized building permit record."""

    permit_number: str
    address: str
    borough: str
    permit_type: str
    residential_units: int | None
    estimated_cost: int | None
    filing_date: datetime | None
    approval_date: datetime | None
    completion_date: datetime | None
    status: str
    latitude: float | None = None
    longitude: float | None = None
    raw_data: dict | None = None


class ATTOMClient:
    """Client for ATTOM Data API with NYC Open Data fallback."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ATTOM_API_KEY", "")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers["apikey"] = self.api_key
            self.session.headers["Accept"] = "application/json"

    @property
    def has_attom_key(self) -> bool:
        return bool(self.api_key)

    def get_permits_by_address(self, address: str) -> list[PermitRecord]:
        """Get building permits for a specific address."""
        if self.has_attom_key:
            try:
                return self._attom_permits_by_address(address)
            except Exception:
                log.warning("ATTOM API failed for %s, falling back to NYC Open Data", address)
        return self._nyc_permits_by_address(address)

    def get_permits_by_geography(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 0.25,
    ) -> list[PermitRecord]:
        """Get building permits within a radius of a coordinate."""
        if self.has_attom_key:
            try:
                return self._attom_permits_by_geo(latitude, longitude, radius_miles)
            except Exception:
                log.warning("ATTOM API failed for geo query, falling back to NYC Open Data")
        return self._nyc_permits_by_geo(latitude, longitude, radius_miles)

    def get_permits_by_borough(
        self,
        borough: str,
        since_date: str | None = None,
        limit: int = 1000,
    ) -> list[PermitRecord]:
        """Get recent permits for a borough (NYC Open Data only)."""
        return self._nyc_permits_by_borough(borough, since_date, limit)

    # ── ATTOM API methods ───────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _attom_permits_by_address(self, address: str) -> list[PermitRecord]:
        resp = self.session.get(
            f"{ATTOM_BASE_URL}/property/buildingpermits",
            params={"address1": address, "address2": "NY"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return self._parse_attom_permits(data)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _attom_permits_by_geo(
        self, lat: float, lng: float, radius: float
    ) -> list[PermitRecord]:
        resp = self.session.get(
            f"{ATTOM_BASE_URL}/property/buildingpermits",
            params={
                "latitude": lat,
                "longitude": lng,
                "radius": radius,
                "searchtype": "radius",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return self._parse_attom_permits(data)

    def _parse_attom_permits(self, data: dict[str, Any]) -> list[PermitRecord]:
        permits = []
        properties = data.get("property", [])
        for prop in properties:
            address_info = prop.get("address", {})
            for permit in prop.get("building", {}).get("permits", []):
                permits.append(PermitRecord(
                    permit_number=permit.get("permitNumber", ""),
                    address=address_info.get("oneLine", ""),
                    borough=_borough_from_county(address_info.get("countrySubd", "")),
                    permit_type=permit.get("permitType", ""),
                    residential_units=_safe_int(permit.get("residentialUnits")),
                    estimated_cost=_safe_int(permit.get("estimatedCost")),
                    filing_date=_parse_date(permit.get("filingDate")),
                    approval_date=_parse_date(permit.get("approvalDate")),
                    completion_date=_parse_date(permit.get("completionDate")),
                    status=permit.get("status", ""),
                    latitude=_safe_float(address_info.get("latitude")),
                    longitude=_safe_float(address_info.get("longitude")),
                    raw_data=permit,
                ))
        return permits

    # ── NYC Open Data fallback methods ──────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _nyc_permits_by_address(self, address: str) -> list[PermitRecord]:
        """Query NYC DOB permits by address."""
        resp = requests.get(
            NYC_OPEN_DATA_URL,
            params={
                "$where": f"upper(house__) || ' ' || upper(street_name) like upper('%{_sanitize(address)}%')",
                "$limit": 50,
                "$order": "filing_date DESC",
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return [self._parse_nyc_permit(r) for r in resp.json()]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _nyc_permits_by_geo(
        self, lat: float, lng: float, radius: float
    ) -> list[PermitRecord]:
        """Query NYC DOB permits by geography (Socrata geo query)."""
        meters = radius * 1609.34  # miles to meters
        resp = requests.get(
            NYC_OPEN_DATA_URL,
            params={
                "$where": f"within_circle(gis_latitude, gis_longitude, {lat}, {lng}, {meters})",
                "$limit": 100,
                "$order": "filing_date DESC",
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return [self._parse_nyc_permit(r) for r in resp.json()]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _nyc_permits_by_borough(
        self, borough: str, since_date: str | None, limit: int
    ) -> list[PermitRecord]:
        """Query NYC DOB permits by borough with optional date filter."""
        borough_code = _nyc_borough_code(borough)
        where_clause = f"borough = '{borough_code}'"
        if since_date:
            where_clause += f" AND filing_date >= '{since_date}'"

        resp = requests.get(
            NYC_OPEN_DATA_URL,
            params={
                "$where": where_clause,
                "$limit": limit,
                "$order": "filing_date DESC",
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return [self._parse_nyc_permit(r) for r in resp.json()]

    def _parse_nyc_permit(self, row: dict[str, Any]) -> PermitRecord:
        house = row.get("house__", "")
        street = row.get("street_name", "")
        address = f"{house} {street}".strip()

        return PermitRecord(
            permit_number=row.get("job__", "") or row.get("permit_si_no", ""),
            address=address,
            borough=_borough_from_code(row.get("borough", "")),
            permit_type=row.get("permit_type", ""),
            residential_units=_safe_int(row.get("residential")),
            estimated_cost=_safe_int(row.get("estimated_job_cost")),
            filing_date=_parse_date(row.get("filing_date")),
            approval_date=_parse_date(row.get("issuance_date")),
            completion_date=None,
            status=row.get("filing_status", ""),
            latitude=_safe_float(row.get("gis_latitude")),
            longitude=_safe_float(row.get("gis_longitude")),
            raw_data=row,
        )


# ── Helpers ─────────────────────────────────────────────────────────────


def _sanitize(s: str) -> str:
    """Sanitize string for Socrata queries — prevent injection."""
    return s.replace("'", "''").replace("%", "").replace("_", "")


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_date(val: str | None) -> datetime | None:
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _borough_from_county(county: str) -> str:
    mapping = {
        "NEW YORK": "Manhattan",
        "KINGS": "Brooklyn",
        "QUEENS": "Queens",
        "BRONX": "Bronx",
        "RICHMOND": "Staten Island",
    }
    return mapping.get(county.upper(), county)


def _borough_from_code(code: str) -> str:
    mapping = {
        "1": "Manhattan",
        "2": "Bronx",
        "3": "Brooklyn",
        "4": "Queens",
        "5": "Staten Island",
        "MANHATTAN": "Manhattan",
        "BRONX": "Bronx",
        "BROOKLYN": "Brooklyn",
        "QUEENS": "Queens",
        "STATEN ISLAND": "Staten Island",
    }
    return mapping.get(code.upper().strip(), code)


def _nyc_borough_code(borough: str) -> str:
    mapping = {
        "MANHATTAN": "1",
        "BRONX": "2",
        "BROOKLYN": "3",
        "QUEENS": "4",
        "STATEN ISLAND": "5",
    }
    return mapping.get(borough.upper(), "1")
