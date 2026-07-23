"""Repair ORM models: RepairOrder, RepairPart."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Numeric,
    ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from src.database import Base


class RepairOrder(Base):
    """維修工單"""
    __tablename__ = "repair_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repair_no = Column(String(50), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    item_name = Column(String(200), nullable=False)       # 送修品名
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    serial_no = Column(String(100), nullable=True)
    fault_desc = Column(Text, nullable=False)             # 故障描述
    status = Column(String(20), nullable=False, default="received")
    # received / diagnosing / repairing / waiting_parts / done / returned
    repair_desc = Column(Text, nullable=True)             # 維修內容
    labor_fee = Column(Numeric(12, 2), default=0)
    parts_fee = Column(Numeric(12, 2), default=0)
    total_fee = Column(Numeric(12, 2), default=0)
    warranty_until = Column(Date, nullable=True)
    received_date = Column(Date, default=date.today)
    completed_date = Column(Date, nullable=True)
    returned_date = Column(Date, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("repair_no", "tenant_id", name="uq_ro_repair_no_tenant"),
    )

    # Relationships
    customer = relationship("Customer")
    creator = relationship("User")
    parts = relationship("RepairPart", back_populates="repair_order", cascade="all, delete-orphan")


class RepairPart(Base):
    """維修零件明細"""
    __tablename__ = "repair_parts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repair_order_id = Column(Integer, ForeignKey("repair_orders.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    part_name = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), default=0)
    amount = Column(Numeric(12, 2), default=0)
    notes = Column(String(200), nullable=True)

    # Relationships
    repair_order = relationship("RepairOrder", back_populates="parts")
    item = relationship("Item")
