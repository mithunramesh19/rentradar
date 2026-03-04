"""PriceHistory model — tracks price changes for listings."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rentradar.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )
    price: Mapped[int] = mapped_column(Integer)
    previous_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(20))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )

    # Relationships
    listing: Mapped["Listing"] = relationship(back_populates="price_history")  # noqa: F821

    def __repr__(self) -> str:
        return f"<PriceHistory(id={self.id}, listing_id={self.listing_id}, price={self.price})>"
