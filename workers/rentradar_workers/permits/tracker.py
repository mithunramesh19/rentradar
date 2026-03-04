"""Permit tracker — daily ingest and proximity alerts.

Ingests new building permits from NYC Open Data (with ATTOM fallback),
stores them in the database, and generates proximity alerts for active listings.
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from rentradar_workers.permits.attom_client import ATTOMClient, PermitRecord

log = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://rentradar:rentradar@localhost:5432/rentradar")

# Alert proximity radius in miles
PROXIMITY_RADIUS_MILES = 0.25
# Only track permit types relevant to rental market
RELEVANT_PERMIT_TYPES = {"NB", "A1", "A2", "DM"}  # New Building, Alteration, Demolition

# Boroughs to ingest
BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]


def ingest_daily_permits(
    db_url: str | None = None,
    days_back: int = 1,
) -> dict:
    """Ingest recent permits from NYC Open Data into the database.

    Args:
        db_url: Database connection string
        days_back: How many days back to look for permits

    Returns:
        dict with counts: new_permits, duplicates_skipped
    """
    db_url = db_url or DB_URL
    engine = create_engine(db_url)
    client = ATTOMClient()

    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    new_permits = 0
    duplicates = 0

    for borough in BOROUGHS:
        try:
            permits = client.get_permits_by_borough(borough, since_date=since_date, limit=500)
            log.info("Fetched %d permits for %s since %s", len(permits), borough, since_date)

            for permit in permits:
                if not permit.permit_number:
                    continue

                with Session(engine) as session:
                    exists = session.execute(
                        text("SELECT 1 FROM building_permits WHERE permit_number = :pn"),
                        {"pn": permit.permit_number},
                    ).fetchone()

                    if exists:
                        duplicates += 1
                        continue

                    _insert_permit(session, permit)
                    session.commit()
                    new_permits += 1

        except Exception:
            log.exception("Failed to ingest permits for %s", borough)

    log.info(
        "Permit ingestion complete: %d new, %d duplicates skipped",
        new_permits, duplicates,
    )
    return {"new_permits": new_permits, "duplicates_skipped": duplicates}


def check_proximity_alerts(
    db_url: str | None = None,
    radius_miles: float = PROXIMITY_RADIUS_MILES,
    days_back: int = 7,
) -> list[dict]:
    """Check for new permits near active listings and generate alerts.

    Returns list of {listing_id, permit_id, distance_miles, permit_type}
    """
    db_url = db_url or DB_URL
    engine = create_engine(db_url)

    since = datetime.now() - timedelta(days=days_back)

    # Get recent permits with coordinates
    with engine.connect() as conn:
        permits = conn.execute(
            text("""
                SELECT id, permit_number, address, permit_type,
                       ST_Y(location::geometry) as lat, ST_X(location::geometry) as lng
                FROM building_permits
                WHERE filing_date >= :since
                  AND location IS NOT NULL
            """),
            {"since": since},
        ).fetchall()

    if not permits:
        log.info("No recent permits with coordinates found")
        return []

    # Get active listings with coordinates
    with engine.connect() as conn:
        listings = conn.execute(
            text("""
                SELECT id, address,
                       ST_Y(location::geometry) as lat, ST_X(location::geometry) as lng
                FROM listings
                WHERE status = 'active'
                  AND location IS NOT NULL
            """),
        ).fetchall()

    if not listings:
        return []

    alerts = []
    for permit in permits:
        p_id, p_num, p_addr, p_type, p_lat, p_lng = permit
        for listing in listings:
            l_id, l_addr, l_lat, l_lng = listing
            dist = _haversine_miles(p_lat, p_lng, l_lat, l_lng)
            if dist <= radius_miles:
                alerts.append({
                    "listing_id": l_id,
                    "permit_id": p_id,
                    "permit_number": p_num,
                    "permit_type": p_type,
                    "permit_address": p_addr,
                    "listing_address": l_addr,
                    "distance_miles": round(dist, 3),
                })

    log.info("Found %d proximity alerts", len(alerts))
    return alerts


def _insert_permit(session: Session, permit: PermitRecord) -> None:
    """Insert a permit record into the database."""
    location_sql = "NULL"
    params: dict = {
        "pn": permit.permit_number,
        "addr": permit.address,
        "borough": permit.borough,
        "ptype": permit.permit_type,
        "units": permit.residential_units,
        "cost": permit.estimated_cost,
        "filing": permit.filing_date,
        "approval": permit.approval_date,
        "completion": permit.completion_date,
        "status": permit.status,
        "raw": permit.raw_data or {},
    }

    if permit.latitude and permit.longitude:
        location_sql = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)"
        params["lat"] = permit.latitude
        params["lng"] = permit.longitude

    session.execute(
        text(f"""
            INSERT INTO building_permits
                (permit_number, address, borough, location, permit_type,
                 residential_units, estimated_cost, filing_date, approval_date,
                 completion_date, status, raw_data, created_at)
            VALUES
                (:pn, :addr, :borough, {location_sql}, :ptype,
                 :units, :cost, :filing, :approval,
                 :completion, :status, CAST(:raw AS jsonb), NOW())
        """),
        params,
    )


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points (in miles)."""
    R = 3959  # Earth radius in miles

    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
