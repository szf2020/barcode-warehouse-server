"""Partner ORM models: Customer, Supplier + Pydantic schemas."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from src.database import Base


# ─── ORM Models ─────────────────────────────────────────────────────────────

class Customer(Base):
    """Customer table."""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    tax_id = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("code", "tenant_id", name="uq_customer_code_tenant"),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="customers")


class Supplier(Base):
    """Supplier table."""
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    tax_id = Column(String(20), nullable=True)
    bank_account = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("code", "tenant_id", name="uq_supplier_code_tenant"),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="suppliers")
    items = relationship("Item", back_populates="supplier_rel")


# ─── Pydantic Schemas ───────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    """Schema for creating a customer."""
    code: str
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""
    code: Optional[str] = None
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None


class CustomerResponse(BaseModel):
    """Schema for customer response."""
    id: int
    code: str
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierCreate(BaseModel):
    """Schema for creating a supplier."""
    code: str
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    bank_account: Optional[str] = None
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    """Schema for updating a supplier."""
    code: Optional[str] = None
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    bank_account: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    """Schema for supplier response."""
    id: int
    code: str
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    bank_account: Optional[str] = None
    notes: Optional[str] = None
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
