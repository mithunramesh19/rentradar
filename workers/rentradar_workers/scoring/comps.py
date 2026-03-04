"""Comp area calculator — median/p25/p75 rent by neighborhood + bedrooms.

Uses Polars for fast aggregation and Redis for caching results.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import polars as pl
import redis
from sqlalchemy import create_engine, text

log = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour
CACHE_PREFIX = "rentradar:comps:"


@dataclass(frozen=True)
class CompStats:
    """Comparable rental statistics for a neighborhood + bedroom count."""

    neighborhood: str
    bedrooms: int
    median: float
    p25: float
    p75: float
    count: int
    avg_sqft: float | None = None
    avg_ppsf: float | None = None  # price per sq ft


def _cache_key(neighborhood: str, bedrooms: int) -> str:
    return f"{CACHE_PREFIX}{neighborhood}:{bedrooms}"


def get_comp_stats(
    neighborhood: str,
    bedrooms: int,
    db_url: str,
    redis_url: str = "redis://localhost:6379/0",
) -> CompStats | None:
    """Get comp stats for a neighborhood + bedroom count, with Redis caching."""
    r = redis.from_url(redis_url)
    key = _cache_key(neighborhood, bedrooms)

    # Check cache
    cached = r.get(key)
    if cached:
        data = json.loads(cached)
        return CompStats(**data)

    # Query database
    stats = compute_comp_stats(neighborhood, bedrooms, db_url)
    if stats is None:
        return None

    # Cache result
    r.setex(key, CACHE_TTL, json.dumps(_stats_to_dict(stats)))
    return stats


def compute_comp_stats(
    neighborhood: str,
    bedrooms: int,
    db_url: str,
) -> CompStats | None:
    """Compute comp statistics from active listings using Polars."""
    engine = create_engine(db_url)

    query = text("""
        SELECT price, sqft, neighborhood, bedrooms
        FROM listings
        WHERE neighborhood = :neighborhood
          AND bedrooms = :bedrooms
          AND status = 'active'
          AND price > 0
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"neighborhood": neighborhood, "bedrooms": bedrooms})
        rows = result.fetchall()

    if not rows:
        return None

    df = pl.DataFrame(
        {
            "price": [r[0] for r in rows],
            "sqft": [r[1] for r in rows],
        }
    )

    return _aggregate_stats(df, neighborhood, bedrooms)


def _aggregate_stats(df: pl.DataFrame, neighborhood: str, bedrooms: int) -> CompStats | None:
    """Compute percentiles and averages from a Polars DataFrame."""
    if df.is_empty():
        return None

    prices = df["price"].cast(pl.Float64)
    count = len(df)

    median = prices.median()
    p25 = prices.quantile(0.25, interpolation="linear")
    p75 = prices.quantile(0.75, interpolation="linear")

    # Compute sqft stats if available
    sqft_col = df["sqft"].cast(pl.Float64, strict=False)
    valid_sqft = sqft_col.drop_nulls().filter(sqft_col.drop_nulls() > 0)

    avg_sqft = valid_sqft.mean() if len(valid_sqft) > 0 else None

    # Price per square foot
    avg_ppsf = None
    if avg_sqft and avg_sqft > 0:
        df_with_ppsf = df.filter(pl.col("sqft").is_not_null() & (pl.col("sqft") > 0)).with_columns(
            (pl.col("price").cast(pl.Float64) / pl.col("sqft").cast(pl.Float64)).alias("ppsf")
        )
        if not df_with_ppsf.is_empty():
            avg_ppsf = round(df_with_ppsf["ppsf"].mean(), 2)

    return CompStats(
        neighborhood=neighborhood,
        bedrooms=bedrooms,
        median=round(median, 2),
        p25=round(p25, 2),
        p75=round(p75, 2),
        count=count,
        avg_sqft=round(avg_sqft, 1) if avg_sqft else None,
        avg_ppsf=avg_ppsf,
    )


def compute_all_comps(db_url: str, redis_url: str = "redis://localhost:6379/0") -> list[CompStats]:
    """Compute and cache comp stats for all neighborhood + bedroom combos."""
    engine = create_engine(db_url)

    query = text("""
        SELECT price, sqft, neighborhood, bedrooms
        FROM listings
        WHERE status = 'active' AND price > 0
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

    if not rows:
        return []

    df = pl.DataFrame(
        {
            "price": [r[0] for r in rows],
            "sqft": [r[1] for r in rows],
            "neighborhood": [r[2] for r in rows],
            "bedrooms": [r[3] for r in rows],
        }
    )

    r = redis.from_url(redis_url)
    results: list[CompStats] = []

    groups = df.group_by(["neighborhood", "bedrooms"])
    for (neighborhood, bedrooms), group_df in groups:
        if neighborhood is None:
            continue
        stats = _aggregate_stats(
            group_df.select(["price", "sqft"]),
            neighborhood,
            bedrooms,
        )
        if stats:
            key = _cache_key(neighborhood, bedrooms)
            r.setex(key, CACHE_TTL, json.dumps(_stats_to_dict(stats)))
            results.append(stats)

    log.info("Computed comps for %d neighborhood+bedroom combos", len(results))
    return results


def _stats_to_dict(stats: CompStats) -> dict[str, Any]:
    return {
        "neighborhood": stats.neighborhood,
        "bedrooms": stats.bedrooms,
        "median": stats.median,
        "p25": stats.p25,
        "p75": stats.p75,
        "count": stats.count,
        "avg_sqft": stats.avg_sqft,
        "avg_ppsf": stats.avg_ppsf,
    }
