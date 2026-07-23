"""Quotation service — business logic for quotations."""

from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from src.models.transaction import Quotation, QuotationLine
from src.services.order_number import generate_order_number


def list_quotations(
    db: Session, tenant_id: int, search: str = "", status: str = ""
) -> List[Quotation]:
    """List quotations with optional filters."""
    query = db.query(Quotation).options(
        joinedload(Quotation.customer),
        joinedload(Quotation.creator),
    ).filter(Quotation.tenant_id == tenant_id)

    if status:
        query = query.filter(Quotation.status == status)
    if search:
        query = query.filter(
            or_(
                Quotation.quote_no.ilike(f"%{search}%"),
                Quotation.notes.ilike(f"%{search}%"),
            )
        )
    return query.order_by(Quotation.quote_date.desc(), Quotation.id.desc()).all()


def get_quotation(db: Session, quotation_id: int, tenant_id: int) -> Optional[Quotation]:
    """Get a single quotation with lines loaded."""
    return db.query(Quotation).options(
        joinedload(Quotation.customer),
        joinedload(Quotation.creator),
        joinedload(Quotation.lines).joinedload(QuotationLine.item),
    ).filter(
        Quotation.id == quotation_id,
        Quotation.tenant_id == tenant_id,
    ).first()


def create_quotation(
    db: Session,
    tenant_id: int,
    user_id: int,
    customer_id: int,
    quote_date: Optional[date] = None,
    valid_until: Optional[date] = None,
    notes: str = "",
) -> Quotation:
    """Create a new quotation (draft)."""
    if quote_date is None:
        quote_date = date.today()

    quote_no = generate_order_number(db, "QT", tenant_id, quote_date)

    qt = Quotation(
        quote_no=quote_no,
        customer_id=customer_id,
        quote_date=quote_date,
        valid_until=valid_until,
        status="draft",
        notes=notes or None,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(qt)
    db.commit()
    db.refresh(qt)
    return qt


def add_line(
    db: Session, quotation_id: int, tenant_id: int,
    item_id: int, quantity: int, unit_price: Decimal,
    notes: str = "",
) -> Optional[QuotationLine]:
    """Add a line item to a quotation."""
    qt = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.tenant_id == tenant_id,
        Quotation.status == "draft",
    ).first()
    if not qt:
        return None

    amount = Decimal(str(quantity)) * unit_price
    line = QuotationLine(
        quotation_id=quotation_id,
        item_id=item_id,
        quantity=quantity,
        unit_price=unit_price,
        amount=amount,
        notes=notes or None,
    )
    db.add(line)
    _recalculate_total(db, qt)
    db.commit()
    return line


def remove_line(db: Session, line_id: int, quotation_id: int, tenant_id: int) -> bool:
    """Remove a line from a quotation."""
    qt = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.tenant_id == tenant_id,
        Quotation.status == "draft",
    ).first()
    if not qt:
        return False

    line = db.query(QuotationLine).filter(
        QuotationLine.id == line_id,
        QuotationLine.quotation_id == quotation_id,
    ).first()
    if not line:
        return False

    db.delete(line)
    _recalculate_total(db, qt)
    db.commit()
    return True


def send_quotation(db: Session, quotation_id: int, tenant_id: int) -> Optional[Quotation]:
    """Mark quotation as sent."""
    qt = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.tenant_id == tenant_id,
        Quotation.status == "draft",
    ).first()
    if not qt or not qt.lines:
        return None

    qt.status = "sent"
    db.commit()
    db.refresh(qt)
    return qt


def accept_quotation(db: Session, quotation_id: int, tenant_id: int) -> Optional[Quotation]:
    """Mark quotation as accepted (can be converted to sales order)."""
    qt = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.tenant_id == tenant_id,
        Quotation.status.in_(["draft", "sent"]),
    ).first()
    if not qt:
        return None

    qt.status = "accepted"
    db.commit()
    db.refresh(qt)
    return qt


def reject_quotation(db: Session, quotation_id: int, tenant_id: int) -> Optional[Quotation]:
    """Mark quotation as rejected."""
    qt = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.tenant_id == tenant_id,
        Quotation.status.in_(["draft", "sent"]),
    ).first()
    if not qt:
        return None

    qt.status = "rejected"
    db.commit()
    db.refresh(qt)
    return qt


def delete_quotation(db: Session, quotation_id: int, tenant_id: int) -> bool:
    """Delete a draft quotation."""
    qt = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.tenant_id == tenant_id,
        Quotation.status == "draft",
    ).first()
    if not qt:
        return False

    db.delete(qt)
    db.commit()
    return True


def _recalculate_total(db: Session, qt: Quotation):
    """Recalculate quotation total from lines."""
    db.flush()
    lines = db.query(QuotationLine).filter(
        QuotationLine.quotation_id == qt.id
    ).all()
    qt.total_amount = sum(line.amount for line in lines)
