"""Base ORM models: Tenant, User."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship

from src.database import Base


class Tenant(Base):
    """Tenant (company) table."""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    users = relationship("User", back_populates="tenant")
    items = relationship("Item", back_populates="tenant")
    categories = relationship("Category", back_populates="tenant")
    customers = relationship("Customer", back_populates="tenant")
    suppliers = relationship("Supplier", back_populates="tenant")


class User(Base):
    """User account table."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # super_admin, tenant_admin, user
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)  # null for super_admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
