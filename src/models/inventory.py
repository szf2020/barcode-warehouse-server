"""Inventory ORM models: InventoryLog, StocktakeSession, StocktakeItem."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from src.database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# ORM Models
# ═══════════════════════════════════════════════════════════════════════════════

class InventoryLog(Base):
    """庫存異動記錄 — 所有出入庫動作皆寫入"""
    __tablename__ = "inventory_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    action = Column(String(20), nullable=False)       # in / out / adjust / stocktake
    quantity = Column(Integer, nullable=False)         # 正數入庫，負數出庫
    before_qty = Column(Integer, nullable=False)
    after_qty = Column(Integer, nullable=False)
    reference_type = Column(String(30), nullable=True)  # purchase_order / sales_order / repair / manual
    reference_id = Column(Integer, nullable=True)
    notes = Column(String(200), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    item = relationship("Item")
    creator = relationship("User")


class StocktakeSession(Base):
    """盤點作業"""
    __tablename__ = "stocktake_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_no = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="open")  # open / counting / closed
    start_time = Column(DateTime, server_default=func.now())
    end_time = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    creator = relationship("User")
    items = relationship("StocktakeItem", back_populates="session", cascade="all, delete-orphan")


class StocktakeItem(Base):
    """盤點明細"""
    __tablename__ = "stocktake_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("stocktake_sessions.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    system_qty = Column(Integer, nullable=False)
    actual_qty = Column(Integer, nullable=True)
    difference = Column(Integer, nullable=True)
    scanned_at = Column(DateTime, server_default=func.now())
    notes = Column(String(200), nullable=True)

    # Relationships
    session = relationship("StocktakeSession", back_populates="items")
    item = relationship("Item")


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class InventoryLogResponse(BaseModel):
    """Schema for inventory log response."""
    id: int
    item_id: int
    action: str
    quantity: int
    before_qty: int
    after_qty: int
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    notes: Optional[str] = None
    tenant_id: int
    created_at: datetime

    class Config:
        from_attributes = True
