"""Quality score — weighted formula (no ML training needed).

Evaluates listing quality based on:
- Photo count and quality indicators
- Square footage presence
- Description length and quality
- Amenity count
- Number of sources cross-listing
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

# Weights for each component (must sum to 1.0)
WEIGHTS = {
    "photos": 0.25,
    "sqft": 0.15,
    "description": 0.25,
    "amenities": 0.20,
    "sources": 0.15,
}

# Thresholds
MIN_DESCRIPTION_LEN = 50
GOOD_DESCRIPTION_LEN = 300
EXCELLENT_DESCRIPTION_LEN = 800
MIN_AMENITIES = 3
GOOD_AMENITIES = 8
EXCELLENT_AMENITIES = 15
MIN_PHOTOS = 1
GOOD_PHOTOS = 5
EXCELLENT_PHOTOS = 12


@dataclass
class QualityBreakdown:
    """Detailed breakdown of quality score components."""

    total: float
    photos_score: float
    sqft_score: float
    description_score: float
    amenities_score: float
    sources_score: float


def compute_quality_score(
    photo_count: int = 0,
    has_sqft: bool = False,
    sqft: int | None = None,
    description: str | None = None,
    amenities: list[str] | None = None,
    source_count: int = 1,
) -> QualityBreakdown:
    """Compute a 0-100 quality score for a listing."""
    photos_score = _score_photos(photo_count)
    sqft_score = _score_sqft(has_sqft, sqft)
    desc_score = _score_description(description)
    amenities_score = _score_amenities(amenities or [])
    sources_score = _score_sources(source_count)

    total = (
        WEIGHTS["photos"] * photos_score
        + WEIGHTS["sqft"] * sqft_score
        + WEIGHTS["description"] * desc_score
        + WEIGHTS["amenities"] * amenities_score
        + WEIGHTS["sources"] * sources_score
    )

    return QualityBreakdown(
        total=round(total, 1),
        photos_score=round(photos_score, 1),
        sqft_score=round(sqft_score, 1),
        description_score=round(desc_score, 1),
        amenities_score=round(amenities_score, 1),
        sources_score=round(sources_score, 1),
    )


def _score_photos(count: int) -> float:
    """Score 0-100 based on photo count."""
    if count <= 0:
        return 0.0
    if count >= EXCELLENT_PHOTOS:
        return 100.0
    if count >= GOOD_PHOTOS:
        return 70.0 + 30.0 * (count - GOOD_PHOTOS) / (EXCELLENT_PHOTOS - GOOD_PHOTOS)
    return 70.0 * count / GOOD_PHOTOS


def _score_sqft(has_sqft: bool, sqft: int | None = None) -> float:
    """Score 0-100 based on square footage info."""
    if not has_sqft or sqft is None:
        return 0.0
    if sqft <= 0:
        return 0.0
    # Having sqft is worth 80 points; reasonable range gets bonus
    base = 80.0
    if 100 <= sqft <= 10000:
        base = 100.0
    return base


def _score_description(description: str | None) -> float:
    """Score 0-100 based on description quality."""
    if not description or len(description.strip()) == 0:
        return 0.0

    text = description.strip()
    length = len(text)

    # Length score (0-60)
    if length >= EXCELLENT_DESCRIPTION_LEN:
        length_score = 60.0
    elif length >= GOOD_DESCRIPTION_LEN:
        length_score = 40.0 + 20.0 * (length - GOOD_DESCRIPTION_LEN) / (
            EXCELLENT_DESCRIPTION_LEN - GOOD_DESCRIPTION_LEN
        )
    elif length >= MIN_DESCRIPTION_LEN:
        length_score = 40.0 * (length - MIN_DESCRIPTION_LEN) / (
            GOOD_DESCRIPTION_LEN - MIN_DESCRIPTION_LEN
        )
    else:
        length_score = 0.0

    # Quality indicators (0-40)
    quality = 0.0
    # Not all caps
    if text != text.upper():
        quality += 10.0
    # Has sentences (periods or exclamation marks)
    if re.search(r"[.!]", text):
        quality += 10.0
    # Mentions specific features
    feature_keywords = [
        "laundry", "dishwasher", "elevator", "doorman", "gym", "roof",
        "renovated", "natural light", "hardwood", "stainless", "granite",
        "marble", "closet", "storage", "parking", "pet", "balcony", "terrace",
    ]
    matches = sum(1 for kw in feature_keywords if kw.lower() in text.lower())
    quality += min(matches * 5.0, 20.0)

    return min(length_score + quality, 100.0)


def _score_amenities(amenities: list[str]) -> float:
    """Score 0-100 based on amenity count."""
    count = len(amenities)
    if count <= 0:
        return 0.0
    if count >= EXCELLENT_AMENITIES:
        return 100.0
    if count >= GOOD_AMENITIES:
        return 70.0 + 30.0 * (count - GOOD_AMENITIES) / (EXCELLENT_AMENITIES - GOOD_AMENITIES)
    return 70.0 * count / GOOD_AMENITIES


def _score_sources(count: int) -> float:
    """Score 0-100 based on how many sources list this property."""
    if count <= 0:
        return 0.0
    if count == 1:
        return 40.0
    if count == 2:
        return 70.0
    if count == 3:
        return 90.0
    return 100.0


def score_listing(listing_data: dict[str, Any]) -> float:
    """Score a listing from a dict (matches Listing model fields).

    Expected keys: photo_count, sqft, description, amenities, source_count
    """
    breakdown = compute_quality_score(
        photo_count=listing_data.get("photo_count", 0),
        has_sqft=listing_data.get("sqft") is not None and listing_data.get("sqft", 0) > 0,
        sqft=listing_data.get("sqft"),
        description=listing_data.get("description"),
        amenities=listing_data.get("amenities", []),
        source_count=listing_data.get("source_count", 1),
    )
    return breakdown.total
