"""Listing model — core entity for rental listings."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rentradar.database import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    address: Mapped[str] = mapped_column(String(500))
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    borough: Mapped[str] = mapped_column(String(20))
    neighborhood: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    price: Mapped[int] = mapped_column(Integer)
    bedrooms: Mapped[int] = mapped_column(SmallInteger)
    bathrooms: Mapped[float] = mapped_column(Float)
    sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)

    amenities: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    undervalue_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rs_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    canonical_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    source_count: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    days_on_market: Mapped[int | None] = mapped_column(Integer, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    sources: Mapped[list["ListingSource"]] = relationship(  # noqa: F821
        back_populates="listing", cascade="all, delete-orphan"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(  # noqa: F821
        back_populates="listing", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        back_populates="listing"
    )

    __table_args__ = (
        Index("ix_listings_location", location, postgresql_using="gist"),
        Index("ix_listings_status", "status"),
        Index("ix_listings_borough", "borough"),
        Index("ix_listings_price", "price"),
        Index("ix_listings_bedrooms", "bedrooms"),
    )

    def __repr__(self) -> str:
        return f"<Listing(id={self.id}, address='{self.address}', price={self.price})>"
