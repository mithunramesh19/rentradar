"""Geo utilities — ported from Geo-Scout."""

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class LocationType(StrEnum):
    LAT_LONG = "lat_long"
    GEOMETRY = "geometry"
    H3 = "h3"
    PLACE_REF = "place_ref"
    ADMIN_REF = "admin_ref"
    TEXT_LOCATION = "text_location"


class LocationRef(BaseModel):
    """Location reference with type tracking — ported from Geo-Scout."""

    type: LocationType
    value: Any

    def is_resolved(self) -> bool:
        return self.type in (LocationType.LAT_LONG, LocationType.GEOMETRY, LocationType.H3)


# Value validation patterns — ported from Geo-Scout scout/detector/patterns.py
VALUE_PATTERNS = {
    "zip": re.compile(r"^\d{5}(-\d{4})?$"),
    "coordinate": re.compile(r"^-?\d{1,3}\.\d{4,}$"),
    "wkt_point": re.compile(r"^POINT\s*\(", re.IGNORECASE),
    "wkt_polygon": re.compile(r"^(MULTI)?POLYGON\s*\(", re.IGNORECASE),
}


def is_valid_nyc_coordinate(lat: float, lng: float) -> bool:
    """Check if coordinates fall within NYC bounding box."""
    from rentradar_common.constants import NYC_BOUNDS

    return (
        NYC_BOUNDS["min_lat"] <= lat <= NYC_BOUNDS["max_lat"]
        and NYC_BOUNDS["min_lng"] <= lng <= NYC_BOUNDS["max_lng"]
    )
