#!/usr/bin/env python3
"""Ingest Manhattan rent-stabilized buildings from HCR PDF into the database.

Usage:
    python data/ingest_hcr.py [--pdf PATH] [--db-url URL] [--dry-run]

Source: 2022 HCR Building Registration File
    https://rentguidelinesboard.cityofnewyork.us/resources/rent-stabilized-building-lists
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import polars as pl
import tabula
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add project root so we can import models
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from rentradar.database import Base  # noqa: E402
from rentradar.models.rent_stabilized import RentStabilizedBuilding  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_PDF = Path.home() / "Rent Project" / "manhattan_rent_stabilized.pdf"
DEFAULT_DB_URL = "postgresql://rentradar:rentradar@localhost:5432/rentradar"

EXPECTED_COLUMNS = [
    "ZIP", "BLDGNO1", "STREET1", "STSUFX1", "BLDGNO2",
    "STREET2", "STSUFX2", "CITY", "COUNTY", "STATUS1",
    "STATUS2", "STATUS3", "BLOCK", "LOT",
]


def extract_tables_from_pdf(pdf_path: Path) -> pl.DataFrame:
    """Extract all tables from the HCR PDF using tabula-py."""
    log.info("Extracting tables from %s (this may take a few minutes)...", pdf_path)

    dfs = tabula.read_pdf(
        str(pdf_path),
        pages="all",
        multiple_tables=True,
        lattice=False,
        stream=True,
        pandas_options={"dtype": str},
    )

    log.info("Extracted %d table chunks from PDF", len(dfs))

    # Convert each pandas DataFrame to polars, normalize columns
    frames: list[pl.DataFrame] = []
    for i, pdf_df in enumerate(dfs):
        # Normalize column names (strip whitespace, uppercase)
        pdf_df.columns = [c.strip().upper().replace(" ", "") for c in pdf_df.columns]

        # Some pages may have slightly different headers; skip non-data tables
        if "ZIP" not in pdf_df.columns or "BLDGNO1" not in pdf_df.columns:
            log.warning("Skipping chunk %d: missing expected columns (%s)", i, list(pdf_df.columns))
            continue

        # Keep only expected columns, filling missing ones
        for col in EXPECTED_COLUMNS:
            if col not in pdf_df.columns:
                pdf_df[col] = None

        pdf_df = pdf_df[EXPECTED_COLUMNS]
        frame = pl.from_pandas(pdf_df)
        frames.append(frame)

    if not frames:
        raise RuntimeError("No valid tables extracted from PDF")

    combined = pl.concat(frames)
    log.info("Combined %d rows from PDF", len(combined))
    return combined


def clean_data(df: pl.DataFrame) -> pl.DataFrame:
    """Clean and validate the extracted data."""
    # Drop rows where ZIP is null or looks like a header row
    df = df.filter(
        pl.col("ZIP").is_not_null()
        & ~pl.col("ZIP").str.contains("(?i)^zip$")
        & pl.col("ZIP").str.contains(r"^\d{5}$")
    )

    # Strip whitespace from all string columns
    for col in df.columns:
        if df[col].dtype == pl.Utf8:
            df = df.with_columns(pl.col(col).str.strip_chars())

    # Replace empty strings with null
    for col in df.columns:
        if df[col].dtype == pl.Utf8:
            df = df.with_columns(
                pl.when(pl.col(col) == "").then(None).otherwise(pl.col(col)).alias(col)
            )

    # Cast numeric columns
    df = df.with_columns([
        pl.col("COUNTY").cast(pl.Int32, strict=False).alias("COUNTY"),
        pl.col("BLOCK").cast(pl.Int32, strict=False).alias("BLOCK"),
        pl.col("LOT").cast(pl.Int32, strict=False).alias("LOT"),
    ])

    # Drop rows with null block/lot (corrupt rows)
    df = df.filter(pl.col("BLOCK").is_not_null() & pl.col("LOT").is_not_null())

    # Compute BBL (Manhattan = borough 1)
    df = df.with_columns(
        (
            pl.lit("1")
            + pl.col("BLOCK").cast(pl.Utf8).str.zfill(5)
            + pl.col("LOT").cast(pl.Utf8).str.zfill(4)
        ).alias("BBL")
    )

    # Deduplicate on BBL (same building shouldn't appear twice)
    before = len(df)
    df = df.unique(subset=["BBL"])
    after = len(df)
    if before != after:
        log.info("Removed %d duplicate BBL entries", before - after)

    log.info("Cleaned data: %d buildings", len(df))
    return df


def load_to_database(df: pl.DataFrame, db_url: str, dry_run: bool = False) -> int:
    """Load cleaned data into PostgreSQL."""
    engine = create_engine(db_url)

    # Create table if not exists
    Base.metadata.create_all(engine, tables=[RentStabilizedBuilding.__table__])

    rows = df.to_dicts()
    log.info("Loading %d buildings into database...", len(rows))

    if dry_run:
        log.info("[DRY RUN] Would insert %d rows. Sample:", len(rows))
        for row in rows[:5]:
            log.info("  %s", row)
        return len(rows)

    inserted = 0
    with Session(engine) as session:
        # Clear existing data for clean reload
        session.execute(text("DELETE FROM rent_stabilized_buildings"))
        session.flush()

        batch: list[RentStabilizedBuilding] = []
        for row in rows:
            building = RentStabilizedBuilding(
                zip_code=row["ZIP"],
                building_number=row["BLDGNO1"] or "",
                street_name=row["STREET1"] or "",
                street_suffix=row.get("STSUFX1"),
                building_number_2=row.get("BLDGNO2"),
                street_name_2=row.get("STREET2"),
                street_suffix_2=row.get("STSUFX2"),
                city=row.get("CITY") or "NEW YORK",
                county_code=row.get("COUNTY") or 62,
                status1=row["STATUS1"] or "MULTIPLE DWELLING A",
                status2=row.get("STATUS2"),
                status3=row.get("STATUS3"),
                block=row["BLOCK"],
                lot=row["LOT"],
                bbl=row["BBL"],
            )
            batch.append(building)

            if len(batch) >= 500:
                session.add_all(batch)
                session.flush()
                inserted += len(batch)
                batch = []

        if batch:
            session.add_all(batch)
            session.flush()
            inserted += len(batch)

        session.commit()

    log.info("Inserted %d rent-stabilized buildings", inserted)
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest HCR rent-stabilized buildings PDF")
    parser.add_argument(
        "--pdf", type=Path, default=DEFAULT_PDF,
        help=f"Path to HCR PDF (default: {DEFAULT_PDF})",
    )
    parser.add_argument(
        "--db-url", type=str, default=DEFAULT_DB_URL,
        help="PostgreSQL connection URL (sync driver)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Extract and clean data without loading to database",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        log.error("PDF not found: %s", args.pdf)
        sys.exit(1)

    df = extract_tables_from_pdf(args.pdf)
    df = clean_data(df)
    count = load_to_database(df, args.db_url, dry_run=args.dry_run)
    log.info("Done. %d buildings processed.", count)


if __name__ == "__main__":
    main()
