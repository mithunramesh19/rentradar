"""ListingSource model — tracks where each listing was scraped from."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rentradar.database import Base


class ListingSource(Base):
    __tablename__ = "listing_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(20))
    source_url: Mapped[str] = mapped_column(String(1000), unique=True)
    source_listing_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    listing: Mapped["Listing"] = relationship(back_populates="sources")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("listing_id", "source", name="uq_listing_source"),
    )

    def __repr__(self) -> str:
        return f"<ListingSource(id={self.id}, source='{self.source}', listing_id={self.listing_id})>"
