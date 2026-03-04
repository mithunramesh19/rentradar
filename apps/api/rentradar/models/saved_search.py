"""SavedSearch model — user-defined search filters with notification preferences."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rentradar.database import Base


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))

    # Filter criteria
    min_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    borough: Mapped[str | None] = mapped_column(String(20), nullable=True)
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    amenities: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    min_undervalue_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_rs_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Notification preferences
    notify_new: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notify_price_drop: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notify_removed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    channels: Mapped[list] = mapped_column(
        JSONB, default=lambda: ["push", "email"], server_default='["push","email"]'
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="saved_searches")  # noqa: F821

    def __repr__(self) -> str:
        return f"<SavedSearch(id={self.id}, name='{self.name}', user_id={self.user_id})>"
