"""BuildingPermit model — NYC DOB building permit data."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rentradar.database import Base


class BuildingPermit(Base):
    __tablename__ = "building_permits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    permit_number: Mapped[str] = mapped_column(String(50), unique=True)
    address: Mapped[str] = mapped_column(String(500))
    borough: Mapped[str] = mapped_column(String(20))
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    permit_type: Mapped[str] = mapped_column(String(30))
    residential_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    filing_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approval_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30))
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_building_permits_location", location, postgresql_using="gist"),
    )

    def __repr__(self) -> str:
        return f"<BuildingPermit(id={self.id}, permit_number='{self.permit_number}')>"
