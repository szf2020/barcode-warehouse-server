"""Sales Order service — business logic for sales orders + quotation conversion."""

from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from src.models.transaction import SalesOrder, SalesOrderLine, Quotation, QuotationLine
from src.models.item import Item
from src.services.order_number import generate_order_number


def list_sales_orders(
    db: Session, tenant_id: int, search: str = "", status: str = ""
) -> List[SalesOrder]:
    """List sales orders with optional filters."""
    query = db.query(SalesOrder).options(
        joinedload(SalesOrder.customer),
        joinedload(SalesOrder.creator),
    ).filter(SalesOrder.tenant_id == tenant_id)

    if status:
        query = query.filter(SalesOrder.status == status)
    if search:
        query = query.filter(
            or_(
                SalesOrder.order_no.ilike(f"%{search}%"),
                SalesOrder.notes.ilike(f"%{search}%"),
            )
        )
    return query.order_by(SalesOrder.order_date.desc(), SalesOrder.id.desc()).all()


def get_sales_order(db: Session, order_id: int, tenant_id: int) -> Optional[SalesOrder]:
    """Get a single sales order with lines loaded."""
    return db.query(SalesOrder).options(
        joinedload(SalesOrder.customer),
        joinedload(SalesOrder.quotation),
        joinedload(SalesOrder.creator),
        joinedload(SalesOrder.lines).joinedload(SalesOrderLine.item),
    ).filter(
        SalesOrder.id == order_id,
        SalesOrder.tenant_id == tenant_id,
    ).first()


def create_sales_order(
    db: Session,
    tenant_id: int,
    user_id: int,
    customer_id: int,
    order_date: Optional[date] = None,
    quotation_id: Optional[int] = None,
    notes: str = "",
) -> SalesOrder:
    """Create a new sales order (draft)."""
    if order_date is None:
        order_date = date.today()

    order_no = generate_order_number(db, "SO", tenant_id, order_date)

    so = SalesOrder(
        order_no=order_no,
        customer_id=customer_id,
        quotation_id=quotation_id,
        order_date=order_date,
        status="draft",
        notes=notes or None,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(so)
    db.commit()
    db.refresh(so)
    return so


def create_from_quotation(
    db: Session, tenant_id: int, user_id: int, quotation_id: int
) -> Optional[SalesOrder]:
    """Create a sales order from an accepted quotation, copying all lines."""
    qt = db.query(Quotation).options(
        joinedload(Quotation.lines),
    ).filter(
        Quotation.id == quotation_id,
        Quotation.tenant_id == tenant_id,
        Quotation.status == "accepted",
    ).first()
    if not qt:
        return None

    order_date = date.today()
    order_no = generate_order_number(db, "SO", tenant_id, order_date)

    so = SalesOrder(
        order_no=order_no,
        customer_id=qt.customer_id,
        quotation_id=qt.id,
        order_date=order_date,
        status="draft",
        notes=f"由報價單 {qt.quote_no} 轉入",
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(so)
    db.flush()  # Get so.id

    # Copy lines from quotation
    total = Decimal("0")
    for qt_line in qt.lines:
        so_line = SalesOrderLine(
            order_id=so.id,
            item_id=qt_line.item_id,
            quantity=qt_line.quantity,
            unit_price=qt_line.unit_price,
            amount=qt_line.amount,
            notes=qt_line.notes,
        )
        db.add(so_line)
        total += qt_line.amount

    so.total_amount = total
    db.commit()
    db.refresh(so)
    return so


def add_line(
    db: Session, order_id: int, tenant_id: int,
    item_id: int, quantity: int, unit_price: Decimal,
    notes: str = "",
) -> Optional[SalesOrderLine]:
    """Add a line item to a sales order."""
    so = db.query(SalesOrder).filter(
        SalesOrder.id == order_id,
        SalesOrder.tenant_id == tenant_id,
        SalesOrder.status == "draft",
    ).first()
    if not so:
        return None

    amount = Decimal(str(quantity)) * unit_price
    line = SalesOrderLine(
        order_id=order_id,
        item_id=item_id,
        quantity=quantity,
        unit_price=unit_price,
        amount=amount,
        notes=notes or None,
    )
    db.add(line)
    _recalculate_total(db, so)
    db.commit()
    return line


def remove_line(db: Session, line_id: int, order_id: int, tenant_id: int) -> bool:
    """Remove a line from a sales order."""
    so = db.query(SalesOrder).filter(
        SalesOrder.id == order_id,
        SalesOrder.tenant_id == tenant_id,
        SalesOrder.status == "draft",
    ).first()
    if not so:
        return False

    line = db.query(SalesOrderLine).filter(
        SalesOrderLine.id == line_id,
        SalesOrderLine.order_id == order_id,
    ).first()
    if not line:
        return False

    db.delete(line)
    _recalculate_total(db, so)
    db.commit()
    return True


def confirm_order(db: Session, order_id: int, tenant_id: int) -> Optional[SalesOrder]:
    """Confirm a draft sales order."""
    so = db.query(SalesOrder).filter(
        SalesOrder.id == order_id,
        SalesOrder.tenant_id == tenant_id,
        SalesOrder.status == "draft",
    ).first()
    if not so or not so.lines:
        return None

    so.status = "confirmed"
    db.commit()
    db.refresh(so)

    # Auto-create receivable
    from src.services.accounting_service import create_receivable_from_sales
    create_receivable_from_sales(db, so)

    return so


def ship_order(db: Session, order_id: int, tenant_id: int) -> Optional[SalesOrder]:
    """Mark a confirmed sales order as shipped (triggers inventory deduction)."""
    so = db.query(SalesOrder).options(
        joinedload(SalesOrder.lines),
    ).filter(
        SalesOrder.id == order_id,
        SalesOrder.tenant_id == tenant_id,
        SalesOrder.status == "confirmed",
    ).first()
    if not so:
        return None

    so.status = "shipped"
    db.commit()
    db.refresh(so)
    return so


def complete_order(db: Session, order_id: int, tenant_id: int) -> Optional[SalesOrder]:
    """Mark a shipped sales order as completed."""
    so = db.query(SalesOrder).filter(
        SalesOrder.id == order_id,
        SalesOrder.tenant_id == tenant_id,
        SalesOrder.status == "shipped",
    ).first()
    if not so:
        return None

    so.status = "completed"
    db.commit()
    db.refresh(so)
    return so


def cancel_order(db: Session, order_id: int, tenant_id: int) -> Optional[SalesOrder]:
    """Cancel a draft or confirmed sales order."""
    so = db.query(SalesOrder).filter(
        SalesOrder.id == order_id,
        SalesOrder.tenant_id == tenant_id,
        SalesOrder.status.in_(["draft", "confirmed"]),
    ).first()
    if not so:
        return None

    so.status = "cancelled"
    db.commit()
    db.refresh(so)
    return so


def delete_order(db: Session, order_id: int, tenant_id: int) -> bool:
    """Delete a draft sales order."""
    so = db.query(SalesOrder).filter(
        SalesOrder.id == order_id,
        SalesOrder.tenant_id == tenant_id,
        SalesOrder.status == "draft",
    ).first()
    if not so:
        return False

    db.delete(so)
    db.commit()
    return True


def _recalculate_total(db: Session, so: SalesOrder):
    """Recalculate order total from lines."""
    db.flush()
    lines = db.query(SalesOrderLine).filter(
        SalesOrderLine.order_id == so.id
    ).all()
    so.total_amount = sum(line.amount for line in lines)
