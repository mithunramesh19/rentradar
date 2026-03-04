"""Rent-stabilized building model (HCR Building Registration File)."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from rentradar.database import Base


class RentStabilizedBuilding(Base):
    """Manhattan buildings containing rent-stabilized units (HCR 2022)."""

    __tablename__ = "rent_stabilized_buildings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    building_number: Mapped[str] = mapped_column(String(20), nullable=False)
    street_name: Mapped[str] = mapped_column(String(100), nullable=False)
    street_suffix: Mapped[str] = mapped_column(String(20), nullable=True)

    # Secondary address (cross-street / alternate entrance)
    building_number_2: Mapped[str | None] = mapped_column(String(20), nullable=True)
    street_name_2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    street_suffix_2: Mapped[str | None] = mapped_column(String(20), nullable=True)

    city: Mapped[str] = mapped_column(String(50), nullable=False, default="NEW YORK")
    county_code: Mapped[int] = mapped_column(Integer, nullable=False, default=62)

    # Dwelling classification
    status1: Mapped[str] = mapped_column(String(50), nullable=False)
    # Tax program / building type (421-A, HOTEL, GARDEN COMPLEX, etc.)
    status2: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Additional classification (ROOMING HOUSE, etc.)
    status3: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Tax lot identifiers
    block: Mapped[int] = mapped_column(Integer, nullable=False)
    lot: Mapped[int] = mapped_column(Integer, nullable=False)
    # Borough-Block-Lot: 1 (Manhattan) + 5-digit block + 4-digit lot
    bbl: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_rs_zip_street", "zip_code", "street_name"),
        Index("ix_rs_block_lot", "block", "lot"),
    )

    @staticmethod
    def compute_bbl(block: int, lot: int, borough: int = 1) -> str:
        """Compute BBL string: borough(1) + block(5, zero-padded) + lot(4, zero-padded)."""
        return f"{borough}{block:05d}{lot:04d}"

    def __repr__(self) -> str:
        return (
            f"<RentStabilizedBuilding {self.building_number} {self.street_name} "
            f"{self.street_suffix or ''}, ZIP {self.zip_code}>"
        )
