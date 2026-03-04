"""Tests for RentStabilizedBuilding model and HCR ingestion logic."""

import polars as pl
import pytest


def test_compute_bbl():
    """BBL = borough(1) + block(5 zero-padded) + lot(4 zero-padded)."""
    from rentradar.models.rent_stabilized import RentStabilizedBuilding

    assert RentStabilizedBuilding.compute_bbl(722, 3) == "1007220003"
    assert RentStabilizedBuilding.compute_bbl(699, 31) == "1006990031"
    assert RentStabilizedBuilding.compute_bbl(829, 1) == "1008290001"
    # Edge case: large block/lot
    assert RentStabilizedBuilding.compute_bbl(99999, 9999) == "1999999999"


def test_compute_bbl_other_borough():
    from rentradar.models.rent_stabilized import RentStabilizedBuilding

    # Brooklyn = borough 3
    assert RentStabilizedBuilding.compute_bbl(100, 50, borough=3) == "3001000050"


def test_model_repr():
    from rentradar.models.rent_stabilized import RentStabilizedBuilding

    b = RentStabilizedBuilding(
        zip_code="10001",
        building_number="246",
        street_name="10TH",
        street_suffix="AVE",
        city="NEW YORK",
        county_code=62,
        status1="MULTIPLE DWELLING A",
        block=722,
        lot=3,
        bbl="1007220003",
    )
    assert "246" in repr(b)
    assert "10TH" in repr(b)
    assert "10001" in repr(b)


def test_clean_data():
    """Test the clean_data function from ingest_hcr."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "data"))
    from ingest_hcr import clean_data

    raw = pl.DataFrame({
        "ZIP": ["10001", "10001", "ZIP", None, "10002", "10001"],
        "BLDGNO1": ["246", "299", "BLDGNO1", "100", "3", "246"],
        "STREET1": ["10TH", "10TH", "STREET1", "MAIN", "ALLEN", "10TH"],
        "STSUFX1": ["AVE", "AVE", "STSUFX1", "ST", "ST", "AVE"],
        "BLDGNO2": [None, None, None, None, None, None],
        "STREET2": [None, None, None, None, None, None],
        "STSUFX2": [None, None, None, None, None, None],
        "CITY": ["NEW YORK", "NEW YORK", "CITY", "NEW YORK", "NEW YORK", "NEW YORK"],
        "COUNTY": ["62", "62", "COUNTY", "62", "62", "62"],
        "STATUS1": [
            "MULTIPLE DWELLING A", "MULTIPLE DWELLING A", "STATUS1",
            "MULTIPLE DWELLING B", "MULTIPLE DWELLING A", "MULTIPLE DWELLING A",
        ],
        "STATUS2": [None, None, None, None, None, None],
        "STATUS3": [None, None, None, None, None, None],
        "BLOCK": ["722", "699", "BLOCK", "100", "293", "722"],
        "LOT": ["3", "31", "LOT", "5", "20", "3"],
    })

    cleaned = clean_data(raw)

    # Header row (ZIP="ZIP") and null ZIP row should be removed
    assert len(cleaned) <= 4  # 4 valid rows, but 2 share same BBL → dedup
    # All remaining rows should have valid zip codes
    zips = cleaned["ZIP"].to_list()
    assert all(z.isdigit() and len(z) == 5 for z in zips)
    # BBL should be computed
    assert "BBL" in cleaned.columns
    bbls = cleaned["BBL"].to_list()
    assert all(len(b) == 10 for b in bbls)
