"""Order number generator — produces sequential document numbers.

Format: {PREFIX}-{YYYYMMDD}-{SEQ:03d}
Examples: PO-20260723-001, QT-20260723-002, SO-20260723-001
"""

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.transaction import PurchaseOrder, Quotation, SalesOrder


def generate_order_number(db: Session, prefix: str, tenant_id: int, order_date: date = None) -> str:
    """Generate next sequential order number for given prefix and date.

    Args:
        db: Database session
        prefix: Order type prefix (PO/QT/SO)
        tenant_id: Tenant ID for isolation
        order_date: Date for the order number (defaults to today)

    Returns:
        Formatted order number like "PO-20260723-001"
    """
    if order_date is None:
        order_date = date.today()

    date_str = order_date.strftime("%Y%m%d")
    like_pattern = f"{prefix}-{date_str}-%"

    # Determine which table to query based on prefix
    model_map = {
        "PO": PurchaseOrder,
        "QT": Quotation,
        "SO": SalesOrder,
    }

    model = model_map.get(prefix)
    if model is None:
        raise ValueError(f"Unknown order prefix: {prefix}")

    # Get the column that holds the order number
    if prefix == "QT":
        no_column = model.quote_no
    else:
        no_column = model.order_no

    # Count existing orders for this date and tenant
    count = db.query(func.count(model.id)).filter(
        no_column.like(like_pattern),
        model.tenant_id == tenant_id,
    ).scalar() or 0

    seq = count + 1
    return f"{prefix}-{date_str}-{seq:03d}"
