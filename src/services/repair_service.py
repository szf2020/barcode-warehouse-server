"""Repair Order service — business logic for repair orders."""

from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from src.models.repair import RepairOrder, RepairPart
from src.models.item import Item


VALID_TRANSITIONS = {
    "received": ["diagnosing", "repairing"],
    "diagnosing": ["repairing", "waiting_parts", "done"],
    "repairing": ["waiting_parts", "done"],
    "waiting_parts": ["repairing", "done"],
    "done": ["returned"],
}


def generate_repair_no(db: Session, tenant_id: int, received_date: date = None) -> str:
    """Generate repair order number: RO-{YYYYMMDD}-{seq}."""
    if received_date is None:
        received_date = date.today()
    date_str = received_date.strftime("%Y%m%d")
    like_pattern = f"RO-{date_str}-%"

    count = db.query(func.count(RepairOrder.id)).filter(
        RepairOrder.repair_no.like(like_pattern),
        RepairOrder.tenant_id == tenant_id,
    ).scalar() or 0

    return f"RO-{date_str}-{count + 1:03d}"


def list_repair_orders(
    db: Session, tenant_id: int, search: str = "", status: str = ""
) -> List[RepairOrder]:
    query = db.query(RepairOrder).options(
        joinedload(RepairOrder.customer),
    ).filter(RepairOrder.tenant_id == tenant_id)

    if status:
        query = query.filter(RepairOrder.status == status)
    if search:
        query = query.filter(
            or_(
                RepairOrder.repair_no.ilike(f"%{search}%"),
                RepairOrder.item_name.ilike(f"%{search}%"),
                RepairOrder.serial_no.ilike(f"%{search}%"),
                RepairOrder.fault_desc.ilike(f"%{search}%"),
            )
        )
    return query.order_by(RepairOrder.received_date.desc(), RepairOrder.id.desc()).all()


def get_repair_order(db: Session, order_id: int, tenant_id: int) -> Optional[RepairOrder]:
    return db.query(RepairOrder).options(
        joinedload(RepairOrder.customer),
        joinedload(RepairOrder.creator),
        joinedload(RepairOrder.parts).joinedload(RepairPart.item),
    ).filter(
        RepairOrder.id == order_id,
        RepairOrder.tenant_id == tenant_id,
    ).first()


def create_repair_order(
    db: Session, tenant_id: int, user_id: int,
    customer_id: int, item_name: str, fault_desc: str,
    brand: str = "", model: str = "", serial_no: str = "",
    warranty_until: date = None, received_date: date = None,
) -> RepairOrder:
    if received_date is None:
        received_date = date.today()

    repair_no = generate_repair_no(db, tenant_id, received_date)
    ro = RepairOrder(
        repair_no=repair_no,
        customer_id=customer_id,
        item_name=item_name,
        brand=brand or None,
        model=model or None,
        serial_no=serial_no or None,
        fault_desc=fault_desc,
        warranty_until=warranty_until,
        received_date=received_date,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(ro)
    db.commit()
    db.refresh(ro)
    return ro


def update_status(db: Session, order_id: int, tenant_id: int, new_status: str) -> Optional[RepairOrder]:
    """Transition repair order to a new status (validates transition)."""
    ro = db.query(RepairOrder).filter(
        RepairOrder.id == order_id,
        RepairOrder.tenant_id == tenant_id,
    ).first()
    if not ro:
        return None

    allowed = VALID_TRANSITIONS.get(ro.status, [])
    if new_status not in allowed:
        return None

    ro.status = new_status
    if new_status == "done":
        ro.completed_date = date.today()
    elif new_status == "returned":
        ro.returned_date = date.today()

    db.commit()
    db.refresh(ro)
    return ro


def update_repair_details(
    db: Session, order_id: int, tenant_id: int,
    repair_desc: str = "", labor_fee: Decimal = Decimal("0"),
) -> Optional[RepairOrder]:
    """Update repair description and labor fee."""
    ro = db.query(RepairOrder).filter(
        RepairOrder.id == order_id,
        RepairOrder.tenant_id == tenant_id,
    ).first()
    if not ro:
        return None

    ro.repair_desc = repair_desc or None
    ro.labor_fee = labor_fee
    _recalculate_fees(db, ro)
    db.commit()
    db.refresh(ro)
    return ro


def add_part(
    db: Session, order_id: int, tenant_id: int,
    part_name: str, quantity: int, unit_price: Decimal,
    item_id: int = None, notes: str = "",
) -> Optional[RepairPart]:
    ro = db.query(RepairOrder).filter(
        RepairOrder.id == order_id,
        RepairOrder.tenant_id == tenant_id,
    ).first()
    if not ro:
        return None

    amount = Decimal(str(quantity)) * unit_price
    part = RepairPart(
        repair_order_id=order_id,
        item_id=item_id,
        part_name=part_name,
        quantity=quantity,
        unit_price=unit_price,
        amount=amount,
        notes=notes or None,
    )
    db.add(part)
    _recalculate_fees(db, ro)
    db.commit()
    return part


def remove_part(db: Session, part_id: int, order_id: int, tenant_id: int) -> bool:
    ro = db.query(RepairOrder).filter(
        RepairOrder.id == order_id,
        RepairOrder.tenant_id == tenant_id,
    ).first()
    if not ro:
        return False

    part = db.query(RepairPart).filter(
        RepairPart.id == part_id,
        RepairPart.repair_order_id == order_id,
    ).first()
    if not part:
        return False

    db.delete(part)
    _recalculate_fees(db, ro)
    db.commit()
    return True


def _recalculate_fees(db: Session, ro: RepairOrder):
    db.flush()
    parts = db.query(RepairPart).filter(RepairPart.repair_order_id == ro.id).all()
    ro.parts_fee = sum(p.amount for p in parts)
    ro.total_fee = ro.labor_fee + ro.parts_fee
