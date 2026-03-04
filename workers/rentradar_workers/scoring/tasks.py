"""Scoring Celery tasks."""

from __future__ import annotations

import logging
import os

from rentradar_workers.celery_app import app

log = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://rentradar:rentradar@localhost:5432/rentradar")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@app.task(name="scoring.ping")
def ping() -> str:
    return "pong"


@app.task(name="scoring.compute_all_comps", bind=True, max_retries=2)
def compute_all_comps(self) -> dict:
    """Recompute comp statistics for all neighborhood+bedroom combos."""
    from rentradar_workers.scoring.comps import compute_all_comps as _compute

    try:
        results = _compute(DB_URL, REDIS_URL)
        return {"status": "ok", "combos_computed": len(results)}
    except Exception as exc:
        log.exception("Failed to compute comps")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scoring.score_undervalue", bind=True)
def score_undervalue(self, listing_id: int) -> dict:
    """Score a single listing for undervalue."""
    from sqlalchemy import create_engine, text

    from rentradar_workers.scoring.comps import get_comp_stats
    from rentradar_workers.scoring.undervalue import build_features, predict_undervalue

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT price, sqft, neighborhood, bedrooms, days_on_market, source_count "
                 "FROM listings WHERE id = :id"),
            {"id": listing_id},
        ).fetchone()

    if not row:
        return {"status": "not_found", "listing_id": listing_id}

    price, sqft, neighborhood, bedrooms, dom, source_count = row

    comp = get_comp_stats(neighborhood, bedrooms, DB_URL, REDIS_URL)
    if not comp:
        return {"status": "no_comps", "listing_id": listing_id}

    features = build_features(
        price=price,
        comp_median=comp.median,
        comp_p25=comp.p25,
        comp_avg_ppsf=comp.avg_ppsf,
        sqft=sqft,
        days_on_market=dom,
        source_count=source_count,
        bedrooms=bedrooms,
    )
    score = predict_undervalue(features)

    # Update listing
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE listings SET undervalue_score = :score WHERE id = :id"),
            {"score": score, "id": listing_id},
        )
        conn.commit()

    return {"status": "ok", "listing_id": listing_id, "undervalue_score": score}


@app.task(name="scoring.score_rent_stabilized", bind=True)
def score_rent_stabilized(self, listing_id: int) -> dict:
    """Score a single listing for rent-stabilization probability."""
    from sqlalchemy import create_engine, text

    from rentradar_workers.scoring.rent_stabilized import build_features, predict_rs_probability

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT address, borough, neighborhood FROM listings WHERE id = :id"),
            {"id": listing_id},
        ).fetchone()

    if not row:
        return {"status": "not_found", "listing_id": listing_id}

    address, borough, neighborhood = row

    # Check HCR match
    hcr_match = False
    with engine.connect() as conn:
        # Simple address matching — normalize and check
        rs_count = conn.execute(
            text("""
                SELECT COUNT(*) FROM rent_stabilized_buildings
                WHERE UPPER(:address) LIKE '%%' || UPPER(building_number) || ' ' || UPPER(street_name) || '%%'
                LIMIT 1
            """),
            {"address": address},
        ).scalar()
        hcr_match = (rs_count or 0) > 0

    features = build_features(
        hcr_match=hcr_match,
        borough=borough,
    )
    probability = predict_rs_probability(features)

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE listings SET rs_probability = :prob WHERE id = :id"),
            {"prob": probability, "id": listing_id},
        )
        conn.commit()

    return {"status": "ok", "listing_id": listing_id, "rs_probability": probability}


@app.task(name="scoring.score_quality", bind=True)
def score_quality(self, listing_id: int) -> dict:
    """Compute quality score for a single listing."""
    from sqlalchemy import create_engine, text

    from rentradar_workers.scoring.quality import compute_quality_score

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT sqft, description, amenities, source_count FROM listings WHERE id = :id"),
            {"id": listing_id},
        ).fetchone()

    if not row:
        return {"status": "not_found", "listing_id": listing_id}

    sqft, description, amenities, source_count = row

    # photo_count not in Listing model yet — default to 0
    breakdown = compute_quality_score(
        photo_count=0,
        has_sqft=sqft is not None and sqft > 0,
        sqft=sqft,
        description=description,
        amenities=amenities or [],
        source_count=source_count or 1,
    )

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE listings SET quality_score = :score WHERE id = :id"),
            {"score": breakdown.total, "id": listing_id},
        )
        conn.commit()

    return {"status": "ok", "listing_id": listing_id, "quality_score": breakdown.total}


@app.task(name="scoring.score_all_listings")
def score_all_listings() -> dict:
    """Batch-score all active listings (comps → undervalue → RS → quality)."""
    from sqlalchemy import create_engine, text

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id FROM listings WHERE status = 'active'")
        ).fetchall()

    listing_ids = [r[0] for r in rows]
    log.info("Scoring %d active listings", len(listing_ids))

    # First refresh comps
    compute_all_comps.delay()

    # Then score each listing
    for lid in listing_ids:
        score_undervalue.delay(lid)
        score_rent_stabilized.delay(lid)
        score_quality.delay(lid)

    return {"status": "ok", "listings_queued": len(listing_ids)}
