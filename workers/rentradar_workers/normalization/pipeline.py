"""Normalization pipeline — clean, parse, and hash raw listings."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


# Street type abbreviation map
_STREET_TYPES: dict[str, str] = {
    "avenue": "Ave",
    "ave": "Ave",
    "av": "Ave",
    "boulevard": "Blvd",
    "blvd": "Blvd",
    "street": "St",
    "st": "St",
    "str": "St",
    "drive": "Dr",
    "dr": "Dr",
    "road": "Rd",
    "rd": "Rd",
    "place": "Pl",
    "pl": "Pl",
    "lane": "Ln",
    "ln": "Ln",
    "court": "Ct",
    "ct": "Ct",
    "terrace": "Ter",
    "ter": "Ter",
    "way": "Way",
    "circle": "Cir",
    "cir": "Cir",
    "parkway": "Pkwy",
    "pkwy": "Pkwy",
    "square": "Sq",
    "sq": "Sq",
}

# Ordinal normalization: 1st, 2nd, 3rd, etc.
_ORDINAL_RE = re.compile(r"\b(\d+)(st|nd|rd|th)\b", re.IGNORECASE)

# Apartment/unit patterns to strip
_APT_RE = re.compile(
    r",?\s*#?\s*(?:apt|apartment|unit|suite|ste|fl|floor|rm|room)\.?\s*[#]?\s*\S+$",
    re.IGNORECASE,
)

# Multi-space collapse
_MULTI_SPACE_RE = re.compile(r"\s+")

# Price extraction: digits, optional comma groups
_PRICE_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{2})?)")

# Sqft extraction
_SQFT_RE = re.compile(r"([\d,]+)\s*(?:sq\.?\s*ft\.?|sf|sqft)", re.IGNORECASE)

# Bedrooms extraction
_BED_RE = re.compile(r"(\d+)\s*(?:bed(?:room)?s?|br|bd)", re.IGNORECASE)
_STUDIO_RE = re.compile(r"\bstudio\b", re.IGNORECASE)

# Bathrooms extraction
_BATH_RE = re.compile(r"([\d.]+)\s*(?:bath(?:room)?s?|ba)", re.IGNORECASE)


@dataclass
class NormalizedListing:
    """Cleaned and parsed listing fields ready for storage."""

    address_clean: str
    canonical_hash: str
    price_cents: int | None
    bedrooms: float | None
    bathrooms: float | None
    sqft: int | None
    extra: dict[str, Any]


def clean_address(raw: str) -> str:
    """Normalize a street address for consistent dedup.

    Steps:
    1. Strip apartment/unit suffix
    2. Normalize street types (Avenue → Ave, etc.)
    3. Collapse whitespace
    4. Title case
    """
    if not raw:
        return ""

    text = raw.strip()

    # Strip apartment/unit
    text = _APT_RE.sub("", text)

    # Normalize ordinals: keep digits only form (e.g. "1st" → "1st" but lowercase)
    text = _ORDINAL_RE.sub(lambda m: f"{m.group(1)}{m.group(2).lower()}", text)

    # Normalize street types
    words = text.split()
    normalized: list[str] = []
    for word in words:
        clean = word.strip(".,")
        lookup = clean.lower()
        if lookup in _STREET_TYPES:
            normalized.append(_STREET_TYPES[lookup])
        else:
            normalized.append(word)
    text = " ".join(normalized)

    # Collapse whitespace
    text = _MULTI_SPACE_RE.sub(" ", text).strip()

    # Title case
    text = text.title()

    return text


def canonical_hash(source: str, address_clean: str, bedrooms: float | None) -> str:
    """Deterministic hash for dedup across sources.

    Combines source + cleaned address + bedrooms to identify the same unit.
    """
    bed_str = str(bedrooms) if bedrooms is not None else "none"
    payload = f"{source}|{address_clean.lower()}|{bed_str}"
    return hashlib.sha256(payload.encode()).hexdigest()


def parse_price(raw: str) -> int | None:
    """Extract price in cents from raw price string. Returns None if unparseable."""
    if not raw:
        return None
    m = _PRICE_RE.search(raw)
    if not m:
        return None
    digits = m.group(1).replace(",", "")
    try:
        dollars = float(digits)
        return int(dollars * 100)
    except ValueError:
        return None


def parse_bedrooms(raw: str) -> float | None:
    """Extract bedroom count. Returns 0 for studio, None if unparseable."""
    if not raw:
        return None
    if _STUDIO_RE.search(raw):
        return 0.0
    m = _BED_RE.search(raw)
    if m:
        return float(m.group(1))
    # Try bare number
    try:
        return float(raw.strip())
    except ValueError:
        return None


def parse_bathrooms(raw: str) -> float | None:
    """Extract bathroom count. Returns None if unparseable."""
    if not raw:
        return None
    m = _BATH_RE.search(raw)
    if m:
        return float(m.group(1))
    try:
        return float(raw.strip())
    except ValueError:
        return None


def parse_sqft(raw: str) -> int | None:
    """Extract square footage as int. Returns None if unparseable."""
    if not raw:
        return None
    m = _SQFT_RE.search(raw)
    if m:
        return int(m.group(1).replace(",", ""))
    # Try bare number
    digits = raw.strip().replace(",", "")
    try:
        return int(digits)
    except ValueError:
        return None


def normalize(
    source: str,
    address: str,
    price: str,
    bedrooms: str,
    bathrooms: str,
    sqft: str,
    **extra: Any,
) -> NormalizedListing:
    """Full normalization pipeline: clean → parse → hash."""
    addr = clean_address(address)
    beds = parse_bedrooms(bedrooms)
    baths = parse_bathrooms(bathrooms)
    sq = parse_sqft(sqft)
    price_cents = parse_price(price)
    chash = canonical_hash(source, addr, beds)

    return NormalizedListing(
        address_clean=addr,
        canonical_hash=chash,
        price_cents=price_cents,
        bedrooms=beds,
        bathrooms=baths,
        sqft=sq,
        extra=extra,
    )
