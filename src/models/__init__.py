"""Models package — re-exports all ORM models and Pydantic schemas."""

from src.models.base import Tenant, User  # noqa: F401
from src.models.item import (  # noqa: F401
    Category,
    Item,
    ItemCreate,
    ItemUpdate,
    ItemResponse,
    CategoryCreate,
    CategoryResponse,
)
from src.models.partner import (  # noqa: F401
    Customer,
    Supplier,
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
)
from src.models.transaction import (  # noqa: F401
    PurchaseOrder,
    PurchaseOrderLine,
    Quotation,
    QuotationLine,
    SalesOrder,
    SalesOrderLine,
    OrderLineCreate,
    OrderLineResponse,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    QuotationCreate,
    QuotationResponse,
    SalesOrderCreate,
    SalesOrderResponse,
)
from src.models.inventory import (  # noqa: F401
    InventoryLog,
    StocktakeSession,
    StocktakeItem,
    InventoryLogResponse,
)
from src.models.accounting import (  # noqa: F401
    Receivable,
    Payable,
    Payment,
    PaymentCreate,
    ReceivableResponse,
    PayableResponse,
)
from src.models.repair import RepairOrder, RepairPart  # noqa: F401

# Pydantic schemas kept here for backward-compatible imports
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TenantCreate(BaseModel):
    """Schema for creating a tenant."""
    name: str
    code: str


class TenantResponse(BaseModel):
    """Schema for tenant response."""
    id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """Schema for creating a user."""
    username: str
    password: str
    display_name: str
    role: str = "user"
    tenant_id: Optional[int] = None


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    username: str
    display_name: str
    role: str
    tenant_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
