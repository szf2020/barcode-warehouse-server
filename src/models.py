"""SQLAlchemy ORM models and Pydantic schemas for warehouse items."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, func
from pydantic import BaseModel

from src.database import Base


# ─── SQLAlchemy ORM Model ───────────────────────────────────────────────────

class Item(Base):
    """Warehouse item table."""
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barcode = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    spec = Column(String(200), nullable=True)
    quantity = Column(Integer, default=0)
    location = Column(String(100), nullable=True)       # 儲位
    supplier = Column(String(200), nullable=True)       # 供應商
    date_in = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── Pydantic Schemas ───────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    """Schema for creating a new item."""
    barcode: str
    name: str
    spec: Optional[str] = None
    quantity: int = 0
    location: Optional[str] = None
    supplier: Optional[str] = None


class ItemUpdate(BaseModel):
    """Schema for updating an existing item."""
    name: Optional[str] = None
    spec: Optional[str] = None
    quantity: Optional[int] = None
    location: Optional[str] = None
    supplier: Optional[str] = None


class ItemResponse(BaseModel):
    """Schema for item response."""
    id: int
    barcode: str
    name: str
    spec: Optional[str] = None
    quantity: int
    location: Optional[str] = None
    supplier: Optional[str] = None
    date_in: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
