"""Item and Category ORM models + Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from src.database import Base


# ─── ORM Models ─────────────────────────────────────────────────────────────

class Category(Base):
    """Item category table."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("name", "tenant_id", name="uq_category_name_tenant"),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="categories")
    items = relationship("Item", back_populates="category")


class Item(Base):
    """Warehouse item table."""
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barcode = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    spec = Column(String(200), nullable=True)
    quantity = Column(Integer, default=0)
    location = Column(String(100), nullable=True)
    supplier = Column(String(200), nullable=True)       # legacy text field
    cost = Column(Numeric(12, 2), default=0)
    price = Column(Numeric(12, 2), default=0)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    date_in = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="items")
    category = relationship("Category", back_populates="items")
    supplier_rel = relationship("Supplier", back_populates="items")


# ─── Pydantic Schemas ───────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    """Schema for creating a new item."""
    barcode: str
    name: str
    spec: Optional[str] = None
    quantity: int = 0
    location: Optional[str] = None
    supplier: Optional[str] = None
    cost: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None


class ItemUpdate(BaseModel):
    """Schema for updating an existing item."""
    name: Optional[str] = None
    spec: Optional[str] = None
    quantity: Optional[int] = None
    location: Optional[str] = None
    supplier: Optional[str] = None
    cost: Optional[Decimal] = None
    price: Optional[Decimal] = None
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None


class ItemResponse(BaseModel):
    """Schema for item response."""
    id: int
    barcode: str
    name: str
    spec: Optional[str] = None
    quantity: int
    location: Optional[str] = None
    supplier: Optional[str] = None
    cost: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None
    tenant_id: int
    date_in: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    """Schema for creating a category."""
    name: str


class CategoryResponse(BaseModel):
    """Schema for category response."""
    id: int
    name: str
    tenant_id: int
    created_at: datetime

    class Config:
        from_attributes = True
