"""Transaction ORM models: PurchaseOrder, Quotation, SalesOrder + line items."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Numeric,
    ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from src.database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# ORM Models
# ═══════════════════════════════════════════════════════════════════════════════

class PurchaseOrder(Base):
    """進貨單主表"""
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(50), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    order_date = Column(Date, nullable=False, default=date.today)
    status = Column(String(20), nullable=False, default="draft")  # draft/confirmed/received/cancelled
    total_amount = Column(Numeric(12, 2), default=0)
    tax_amount = Column(Numeric(12, 2), default=0)
    notes = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("order_no", "tenant_id", name="uq_po_order_no_tenant"),
    )

    # Relationships
    supplier = relationship("Supplier")
    creator = relationship("User")
    lines = relationship("PurchaseOrderLine", back_populates="order", cascade="all, delete-orphan")


class PurchaseOrderLine(Base):
    """進貨單明細"""
    __tablename__ = "purchase_order_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    received_qty = Column(Integer, default=0)
    notes = Column(String(200), nullable=True)

    # Relationships
    order = relationship("PurchaseOrder", back_populates="lines")
    item = relationship("Item")


class Quotation(Base):
    """報價單主表"""
    __tablename__ = "quotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quote_no = Column(String(50), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    quote_date = Column(Date, nullable=False, default=date.today)
    valid_until = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="draft")  # draft/sent/accepted/rejected/expired
    total_amount = Column(Numeric(12, 2), default=0)
    tax_amount = Column(Numeric(12, 2), default=0)
    notes = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("quote_no", "tenant_id", name="uq_qt_quote_no_tenant"),
    )

    # Relationships
    customer = relationship("Customer")
    creator = relationship("User")
    lines = relationship("QuotationLine", back_populates="quotation", cascade="all, delete-orphan")


class QuotationLine(Base):
    """報價單明細"""
    __tablename__ = "quotation_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    notes = Column(String(200), nullable=True)

    # Relationships
    quotation = relationship("Quotation", back_populates="lines")
    item = relationship("Item")


class SalesOrder(Base):
    """銷貨單主表"""
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(50), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)  # 可由報價單轉入
    order_date = Column(Date, nullable=False, default=date.today)
    status = Column(String(20), nullable=False, default="draft")  # draft/confirmed/shipped/completed/cancelled
    total_amount = Column(Numeric(12, 2), default=0)
    tax_amount = Column(Numeric(12, 2), default=0)
    notes = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("order_no", "tenant_id", name="uq_so_order_no_tenant"),
    )

    # Relationships
    customer = relationship("Customer")
    quotation = relationship("Quotation")
    creator = relationship("User")
    lines = relationship("SalesOrderLine", back_populates="order", cascade="all, delete-orphan")


class SalesOrderLine(Base):
    """銷貨單明細"""
    __tablename__ = "sales_order_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    notes = Column(String(200), nullable=True)

    # Relationships
    order = relationship("SalesOrder", back_populates="lines")
    item = relationship("Item")


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class OrderLineCreate(BaseModel):
    """Schema for creating an order line."""
    item_id: int
    quantity: int = 1
    unit_price: Decimal = Decimal("0")
    notes: Optional[str] = None


class OrderLineResponse(BaseModel):
    """Schema for order line response."""
    id: int
    item_id: int
    quantity: int
    unit_price: Decimal
    amount: Decimal
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class PurchaseOrderCreate(BaseModel):
    """Schema for creating a purchase order."""
    supplier_id: int
    order_date: Optional[date] = None
    notes: Optional[str] = None
    lines: List[OrderLineCreate] = []


class PurchaseOrderResponse(BaseModel):
    """Schema for purchase order response."""
    id: int
    order_no: str
    supplier_id: int
    order_date: date
    status: str
    total_amount: Decimal
    tax_amount: Decimal
    notes: Optional[str] = None
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuotationCreate(BaseModel):
    """Schema for creating a quotation."""
    customer_id: int
    quote_date: Optional[date] = None
    valid_until: Optional[date] = None
    notes: Optional[str] = None
    lines: List[OrderLineCreate] = []


class QuotationResponse(BaseModel):
    """Schema for quotation response."""
    id: int
    quote_no: str
    customer_id: int
    quote_date: date
    valid_until: Optional[date] = None
    status: str
    total_amount: Decimal
    tax_amount: Decimal
    notes: Optional[str] = None
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SalesOrderCreate(BaseModel):
    """Schema for creating a sales order."""
    customer_id: int
    quotation_id: Optional[int] = None
    order_date: Optional[date] = None
    notes: Optional[str] = None
    lines: List[OrderLineCreate] = []


class SalesOrderResponse(BaseModel):
    """Schema for sales order response."""
    id: int
    order_no: str
    customer_id: int
    quotation_id: Optional[int] = None
    order_date: date
    status: str
    total_amount: Decimal
    tax_amount: Decimal
    notes: Optional[str] = None
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
