"""Listings endpoints — search, detail, comps, stats."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_X, ST_Y
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rentradar.database import get_db
from rentradar.models.listing import Listing
from rentradar.models.listing_source import ListingSource
from rentradar.models.price_history import PriceHistory
from rentradar.models.rent_stabilized import RentStabilizedBuilding
from rentradar_common.schemas import (
    ListingDetailResponse,
    ListingResponse,
    PaginatedResponse,
    PriceHistoryResponse,
)

router = APIRouter(prefix="/listings", tags=["listings"])

METERS_PER_MILE = 1609.34

SORT_COLUMNS = {
    "price": Listing.price,
    "undervalue_score": Listing.undervalue_score,
    "rs_probability": Listing.rs_probability,
    "days_on_market": Listing.days_on_market,
    "created_at": Listing.created_at,
}


@router.get("", response_model=PaginatedResponse[ListingResponse])
async def list_listings(
    db: Annotated[AsyncSession, Depends(get_db)],
    min_price: int | None = None,
    max_price: int | None = None,
    bedrooms: Annotated[list[int] | None, Query()] = None,
    borough: str | None = None,
    neighborhood: str | None = None,
    amenities: Annotated[list[str] | None, Query()] = None,
    min_undervalue_score: float | None = None,
    min_rs_probability: float | None = None,
    status: str = "active",
    lat: float | None = None,
    lng: float | None = None,
    radius_miles: float | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    """Search listings with filters, geo-distance, pagination."""
    query = select(Listing)
    count_query = select(func.count()).select_from(Listing)

    # Build filters
    filters = []

    if status:
        filters.append(Listing.status == status)
    if min_price is not None:
        filters.append(Listing.price >= min_price)
    if max_price is not None:
        filters.append(Listing.price <= max_price)
    if bedrooms:
        filters.append(Listing.bedrooms.in_(bedrooms))
    if borough:
        filters.append(Listing.borough == borough)
    if neighborhood:
        filters.append(Listing.neighborhood == neighborhood)
    if min_undervalue_score is not None:
        filters.append(Listing.undervalue_score >= min_undervalue_score)
    if min_rs_probability is not None:
        filters.append(Listing.rs_probability >= min_rs_probability)
    if amenities:
        filters.append(Listing.amenities.op("@>")(json.dumps(amenities)))

    # Geo-distance filter
    if lat is not None and lng is not None and radius_miles is not None:
        point = func.ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        filters.append(
            ST_DWithin(
                func.cast(Listing.location, func.Geography),
                func.cast(point, func.Geography),
                radius_miles * METERS_PER_MILE,
            )
        )

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    # Total count
    total = (await db.execute(count_query)).scalar_one()

    # Sorting
    sort_col = SORT_COLUMNS.get(sort_by, Listing.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    listings = result.scalars().all()

    # Convert to response, extracting lat/lng from PostGIS geometry
    items = []
    for listing in listings:
        data = ListingResponse.model_validate(listing)
        if listing.location is not None:
            # Extract lat/lng from WKB geometry
            coord_result = await db.execute(
                select(
                    ST_X(listing.location).label("lng"),
                    ST_Y(listing.location).label("lat"),
                )
            )
            coords = coord_result.one()
            data.lat = coords.lat
            data.lng = coords.lng
        items.append(data)

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return PaginatedResponse[ListingResponse](
        items=items, total=total, page=page, per_page=per_page, pages=pages
    )


@router.get("/stats")
async def listing_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    borough: str | None = None,
):
    """Neighborhood-level aggregate statistics."""
    query = select(
        Listing.borough,
        Listing.neighborhood,
        func.count().label("count"),
        func.avg(Listing.price).label("avg_price"),
        func.min(Listing.price).label("min_price"),
        func.max(Listing.price).label("max_price"),
        func.avg(Listing.undervalue_score).label("avg_undervalue_score"),
    ).where(Listing.status == "active")

    if borough:
        query = query.where(Listing.borough == borough)

    query = query.group_by(Listing.borough, Listing.neighborhood)
    query = query.order_by(Listing.borough, Listing.neighborhood)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "borough": row.borough,
            "neighborhood": row.neighborhood,
            "count": row.count,
            "avg_price": round(float(row.avg_price), 2) if row.avg_price else None,
            "min_price": row.min_price,
            "max_price": row.max_price,
            "avg_undervalue_score": (
                round(float(row.avg_undervalue_score), 4) if row.avg_undervalue_score else None
            ),
        }
        for row in rows
    ]


@router.get("/{listing_id}", response_model=ListingDetailResponse)
async def get_listing(
    listing_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get listing detail with sources, price history, and RS proximity."""
    query = (
        select(Listing)
        .options(selectinload(Listing.sources), selectinload(Listing.price_history))
        .where(Listing.id == listing_id)
    )
    result = await db.execute(query)
    listing = result.scalar_one_or_none()

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    data = ListingDetailResponse.model_validate(listing)

    # Extract lat/lng
    if listing.location is not None:
        coord_result = await db.execute(
            select(
                ST_X(listing.location).label("lng"),
                ST_Y(listing.location).label("lat"),
            )
        )
        coords = coord_result.one()
        data.lat = coords.lat
        data.lng = coords.lng

        # Check for nearby rent-stabilized buildings (within 200m)
        point = listing.location
        rs_count = await db.execute(
            select(func.count()).select_from(RentStabilizedBuilding)
        )
        data.rs_nearby = (rs_count.scalar_one() or 0) > 0

    return data


@router.get("/{listing_id}/similar", response_model=list[ListingResponse])
async def get_similar_listings(
    listing_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=5, ge=1, le=20),
):
    """Find comparable listings based on price, bedrooms, and location."""
    # Get the reference listing
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Find similar: same borough, similar bedrooms, price within 30%
    price_low = int(listing.price * 0.7)
    price_high = int(listing.price * 1.3)

    query = (
        select(Listing)
        .where(
            Listing.id != listing_id,
            Listing.status == "active",
            Listing.borough == listing.borough,
            Listing.bedrooms.between(listing.bedrooms - 1, listing.bedrooms + 1),
            Listing.price.between(price_low, price_high),
        )
        .order_by(func.abs(Listing.price - listing.price))
        .limit(limit)
    )

    result = await db.execute(query)
    similar = result.scalars().all()

    return [ListingResponse.model_validate(s) for s in similar]
