"""Accounting ORM models: Receivable, Payable, Payment."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey, func
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from src.database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# ORM Models
# ═══════════════════════════════════════════════════════════════════════════════

class Receivable(Base):
    """應收帳款（銷貨確認產生）"""
    __tablename__ = "receivables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    paid_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(20), nullable=False, default="unpaid")  # unpaid/partial/paid/overdue
    due_date = Column(Date, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    sales_order = relationship("SalesOrder")
    customer = relationship("Customer")


class Payable(Base):
    """應付帳款（進貨確認產生）"""
    __tablename__ = "payables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    paid_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(20), nullable=False, default="unpaid")  # unpaid/partial/paid/overdue
    due_date = Column(Date, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    purchase_order = relationship("PurchaseOrder")
    supplier = relationship("Supplier")


class Payment(Base):
    """收付款記錄"""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_type = Column(String(10), nullable=False)     # receive / pay
    reference_type = Column(String(20), nullable=False)   # receivable / payable
    reference_id = Column(Integer, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(20), default="cash")   # cash / transfer / check
    payment_date = Column(Date, nullable=False, default=date.today)
    notes = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    creator = relationship("User")


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class PaymentCreate(BaseModel):
    """Schema for recording a payment."""
    amount: Decimal
    payment_method: str = "cash"
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class ReceivableResponse(BaseModel):
    id: int
    sales_order_id: int
    customer_id: int
    amount: Decimal
    paid_amount: Decimal
    status: str
    due_date: Optional[date] = None
    tenant_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PayableResponse(BaseModel):
    id: int
    purchase_order_id: int
    supplier_id: int
    amount: Decimal
    paid_amount: Decimal
    status: str
    due_date: Optional[date] = None
    tenant_id: int
    created_at: datetime

    class Config:
        from_attributes = True
