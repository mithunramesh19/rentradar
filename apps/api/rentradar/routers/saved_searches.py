"""Saved searches endpoints — CRUD + dry-run test."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rentradar.database import get_db
from rentradar.models.listing import Listing
from rentradar.models.saved_search import SavedSearch
from rentradar.models.user import User
from rentradar.routers.auth import get_current_user
from rentradar_common.schemas import ListingResponse, SavedSearchCreate, SavedSearchResponse

router = APIRouter(prefix="/searches", tags=["saved-searches"])


@router.get("", response_model=list[SavedSearchResponse])
async def list_saved_searches(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """List all saved searches for the authenticated user."""
    result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.user_id == user.id, SavedSearch.is_active.is_(True))
        .order_by(SavedSearch.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=SavedSearchResponse, status_code=201)
async def create_saved_search(
    body: SavedSearchCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Create a new saved search."""
    search = SavedSearch(user_id=user.id, **body.model_dump())
    db.add(search)
    await db.commit()
    await db.refresh(search)
    return search


@router.get("/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Get a specific saved search."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
    )
    search = result.scalar_one_or_none()
    if search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return search


@router.put("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: int,
    body: SavedSearchCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Update a saved search."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
    )
    search = result.scalar_one_or_none()
    if search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    for key, value in body.model_dump().items():
        setattr(search, key, value)

    await db.commit()
    await db.refresh(search)
    return search


@router.delete("/{search_id}", status_code=204)
async def delete_saved_search(
    search_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Soft-delete a saved search (set is_active=False)."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
    )
    search = result.scalar_one_or_none()
    if search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    search.is_active = False
    await db.commit()


@router.post("/{search_id}/test", response_model=list[ListingResponse])
async def test_saved_search(
    search_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Dry-run a saved search to preview matching listings (max 10)."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
    )
    search = result.scalar_one_or_none()
    if search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Build query from saved search filters
    query = select(Listing).where(Listing.status == "active")

    if search.min_price is not None:
        query = query.where(Listing.price >= search.min_price)
    if search.max_price is not None:
        query = query.where(Listing.price <= search.max_price)
    if search.bedrooms is not None:
        query = query.where(Listing.bedrooms == search.bedrooms)
    if search.borough is not None:
        query = query.where(Listing.borough == search.borough)
    if search.amenities:
        query = query.where(Listing.amenities.op("@>")(json.dumps(search.amenities)))
    if search.min_undervalue_score is not None:
        query = query.where(Listing.undervalue_score >= search.min_undervalue_score)
    if search.min_rs_probability is not None:
        query = query.where(Listing.rs_probability >= search.min_rs_probability)

    # Geo filter
    if search.center_lat and search.center_lng and search.radius_miles:
        from geoalchemy2.functions import ST_DWithin, ST_MakePoint

        point = func.ST_SetSRID(ST_MakePoint(search.center_lng, search.center_lat), 4326)
        query = query.where(
            ST_DWithin(
                func.cast(Listing.location, func.Geography),
                func.cast(point, func.Geography),
                search.radius_miles * 1609.34,
            )
        )

    query = query.order_by(Listing.created_at.desc()).limit(10)
    result = await db.execute(query)
    listings = result.scalars().all()

    return [ListingResponse.model_validate(l) for l in listings]
