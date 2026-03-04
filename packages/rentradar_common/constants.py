"""RentRadar constants."""

from enum import StrEnum


class Borough(StrEnum):
    MANHATTAN = "Manhattan"
    BROOKLYN = "Brooklyn"
    QUEENS = "Queens"
    BRONX = "Bronx"
    STATEN_ISLAND = "Staten Island"


class ListingSource(StrEnum):
    STREETEASY = "streeteasy"
    CRAIGSLIST = "craigslist"
    ZILLOW = "zillow"
    RENTCOM = "rentcom"
    ZUMPER = "zumper"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"
    RENTED = "rented"


class EventType(StrEnum):
    LISTED = "listed"
    PRICE_DROP = "price_drop"
    PRICE_INCREASE = "price_increase"
    RELISTED = "relisted"
    REMOVED = "removed"


class NotificationChannel(StrEnum):
    PUSH = "push"
    EMAIL = "email"
    SSE = "sse"


# NYC bounding box for validation
NYC_BOUNDS = {
    "min_lat": 40.4774,
    "max_lat": 40.9176,
    "min_lng": -74.2591,
    "max_lng": -73.7004,
}

# Default scraper schedule (hours between runs)
DEFAULT_SCRAPE_INTERVALS = {
    ListingSource.STREETEASY: 6,
    ListingSource.CRAIGSLIST: 2,
    ListingSource.ZILLOW: 12,
    ListingSource.RENTCOM: 8,
    ListingSource.ZUMPER: 8,
}
