"""Purchase Order service — business logic for purchase orders."""

from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from src.models.transaction import PurchaseOrder, PurchaseOrderLine
from src.models.item import Item
from src.services.order_number import generate_order_number


def list_purchase_orders(
    db: Session, tenant_id: int, search: str = "", status: str = ""
) -> List[PurchaseOrder]:
    """List purchase orders with optional filters."""
    query = db.query(PurchaseOrder).options(
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.creator),
    ).filter(PurchaseOrder.tenant_id == tenant_id)

    if status:
        query = query.filter(PurchaseOrder.status == status)
    if search:
        query = query.filter(
            or_(
                PurchaseOrder.order_no.ilike(f"%{search}%"),
                PurchaseOrder.notes.ilike(f"%{search}%"),
            )
        )
    return query.order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc()).all()


def get_purchase_order(db: Session, order_id: int, tenant_id: int) -> Optional[PurchaseOrder]:
    """Get a single purchase order with lines loaded."""
    return db.query(PurchaseOrder).options(
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.creator),
        joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.item),
    ).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.tenant_id == tenant_id,
    ).first()


def create_purchase_order(
    db: Session,
    tenant_id: int,
    user_id: int,
    supplier_id: int,
    order_date: Optional[date] = None,
    notes: str = "",
) -> PurchaseOrder:
    """Create a new purchase order (draft)."""
    if order_date is None:
        order_date = date.today()

    order_no = generate_order_number(db, "PO", tenant_id, order_date)

    po = PurchaseOrder(
        order_no=order_no,
        supplier_id=supplier_id,
        order_date=order_date,
        status="draft",
        notes=notes or None,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(po)
    db.commit()
    db.refresh(po)
    return po


def add_line(
    db: Session, order_id: int, tenant_id: int,
    item_id: int, quantity: int, unit_price: Decimal,
    notes: str = "",
) -> Optional[PurchaseOrderLine]:
    """Add a line item to a purchase order."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.tenant_id == tenant_id,
        PurchaseOrder.status == "draft",
    ).first()
    if not po:
        return None

    amount = Decimal(str(quantity)) * unit_price
    line = PurchaseOrderLine(
        order_id=order_id,
        item_id=item_id,
        quantity=quantity,
        unit_price=unit_price,
        amount=amount,
        notes=notes or None,
    )
    db.add(line)

    # Recalculate total
    _recalculate_total(db, po)
    db.commit()
    return line


def remove_line(db: Session, line_id: int, order_id: int, tenant_id: int) -> bool:
    """Remove a line from a purchase order."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.tenant_id == tenant_id,
        PurchaseOrder.status == "draft",
    ).first()
    if not po:
        return False

    line = db.query(PurchaseOrderLine).filter(
        PurchaseOrderLine.id == line_id,
        PurchaseOrderLine.order_id == order_id,
    ).first()
    if not line:
        return False

    db.delete(line)
    _recalculate_total(db, po)
    db.commit()
    return True


def confirm_order(db: Session, order_id: int, tenant_id: int) -> Optional[PurchaseOrder]:
    """Confirm a draft purchase order → status becomes 'confirmed'."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.tenant_id == tenant_id,
        PurchaseOrder.status == "draft",
    ).first()
    if not po:
        return None
    if not po.lines:
        return None  # Cannot confirm empty order

    po.status = "confirmed"
    db.commit()
    db.refresh(po)

    # Auto-create payable
    from src.services.accounting_service import create_payable_from_purchase
    create_payable_from_purchase(db, po)

    return po


def receive_order(db: Session, order_id: int, tenant_id: int) -> Optional[PurchaseOrder]:
    """Mark a confirmed purchase order as received (triggers inventory update)."""
    po = db.query(PurchaseOrder).options(
        joinedload(PurchaseOrder.lines)
    ).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.tenant_id == tenant_id,
        PurchaseOrder.status == "confirmed",
    ).first()
    if not po:
        return None

    po.status = "received"
    # Mark all lines as fully received
    for line in po.lines:
        line.received_qty = line.quantity

    db.commit()
    db.refresh(po)
    return po


def cancel_order(db: Session, order_id: int, tenant_id: int) -> Optional[PurchaseOrder]:
    """Cancel a draft or confirmed purchase order."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.tenant_id == tenant_id,
        PurchaseOrder.status.in_(["draft", "confirmed"]),
    ).first()
    if not po:
        return None

    po.status = "cancelled"
    db.commit()
    db.refresh(po)
    return po


def delete_order(db: Session, order_id: int, tenant_id: int) -> bool:
    """Delete a draft purchase order."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.tenant_id == tenant_id,
        PurchaseOrder.status == "draft",
    ).first()
    if not po:
        return False

    db.delete(po)
    db.commit()
    return True


def _recalculate_total(db: Session, po: PurchaseOrder):
    """Recalculate order total from lines."""
    db.flush()
    lines = db.query(PurchaseOrderLine).filter(
        PurchaseOrderLine.order_id == po.id
    ).all()
    po.total_amount = sum(line.amount for line in lines)
