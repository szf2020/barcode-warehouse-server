"""Accounting service — receivables, payables, payments logic."""

from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from src.models.accounting import Receivable, Payable, Payment
from src.models.transaction import SalesOrder, PurchaseOrder


# ─── Auto-creation (called from order confirm) ───────────────────────────────

def create_receivable_from_sales(db: Session, so: SalesOrder, due_date: date = None):
    """Create a receivable when a sales order is confirmed."""
    existing = db.query(Receivable).filter(
        Receivable.sales_order_id == so.id
    ).first()
    if existing:
        return existing

    rec = Receivable(
        sales_order_id=so.id,
        customer_id=so.customer_id,
        amount=so.total_amount,
        paid_amount=Decimal("0"),
        status="unpaid",
        due_date=due_date,
        tenant_id=so.tenant_id,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def create_payable_from_purchase(db: Session, po: PurchaseOrder, due_date: date = None):
    """Create a payable when a purchase order is confirmed."""
    existing = db.query(Payable).filter(
        Payable.purchase_order_id == po.id
    ).first()
    if existing:
        return existing

    pay = Payable(
        purchase_order_id=po.id,
        supplier_id=po.supplier_id,
        amount=po.total_amount,
        paid_amount=Decimal("0"),
        status="unpaid",
        due_date=due_date,
        tenant_id=po.tenant_id,
    )
    db.add(pay)
    db.commit()
    db.refresh(pay)
    return pay


# ─── Listing ─────────────────────────────────────────────────────────────────

def list_receivables(db: Session, tenant_id: int, status: str = "") -> List[Receivable]:
    query = db.query(Receivable).options(
        joinedload(Receivable.customer),
        joinedload(Receivable.sales_order),
    ).filter(Receivable.tenant_id == tenant_id)
    if status:
        query = query.filter(Receivable.status == status)
    return query.order_by(Receivable.created_at.desc()).all()


def list_payables(db: Session, tenant_id: int, status: str = "") -> List[Payable]:
    query = db.query(Payable).options(
        joinedload(Payable.supplier),
        joinedload(Payable.purchase_order),
    ).filter(Payable.tenant_id == tenant_id)
    if status:
        query = query.filter(Payable.status == status)
    return query.order_by(Payable.created_at.desc()).all()


def list_payments(db: Session, tenant_id: int, reference_type: str = "", limit: int = 50) -> List[Payment]:
    query = db.query(Payment).options(
        joinedload(Payment.creator),
    ).filter(Payment.tenant_id == tenant_id)
    if reference_type:
        query = query.filter(Payment.reference_type == reference_type)
    return query.order_by(Payment.created_at.desc()).limit(limit).all()


# ─── Payment recording ───────────────────────────────────────────────────────

def record_receive_payment(
    db: Session, receivable_id: int, tenant_id: int, user_id: int,
    amount: Decimal, method: str = "cash", payment_date: date = None, notes: str = ""
) -> Optional[Payment]:
    """Record a payment received from customer."""
    rec = db.query(Receivable).filter(
        Receivable.id == receivable_id,
        Receivable.tenant_id == tenant_id,
        Receivable.status.in_(["unpaid", "partial"]),
    ).first()
    if not rec:
        return None

    if payment_date is None:
        payment_date = date.today()

    payment = Payment(
        payment_type="receive",
        reference_type="receivable",
        reference_id=rec.id,
        amount=amount,
        payment_method=method,
        payment_date=payment_date,
        notes=notes or None,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(payment)

    rec.paid_amount += amount
    if rec.paid_amount >= rec.amount:
        rec.status = "paid"
    else:
        rec.status = "partial"

    db.commit()
    return payment


def record_pay_payment(
    db: Session, payable_id: int, tenant_id: int, user_id: int,
    amount: Decimal, method: str = "cash", payment_date: date = None, notes: str = ""
) -> Optional[Payment]:
    """Record a payment made to supplier."""
    pay = db.query(Payable).filter(
        Payable.id == payable_id,
        Payable.tenant_id == tenant_id,
        Payable.status.in_(["unpaid", "partial"]),
    ).first()
    if not pay:
        return None

    if payment_date is None:
        payment_date = date.today()

    payment = Payment(
        payment_type="pay",
        reference_type="payable",
        reference_id=pay.id,
        amount=amount,
        payment_method=method,
        payment_date=payment_date,
        notes=notes or None,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(payment)

    pay.paid_amount += amount
    if pay.paid_amount >= pay.amount:
        pay.status = "paid"
    else:
        pay.status = "partial"

    db.commit()
    return payment


# ─── Summary ─────────────────────────────────────────────────────────────────

def get_summary(db: Session, tenant_id: int) -> dict:
    """Get accounting summary: total receivable/payable, overdue counts."""
    from sqlalchemy import func as sqlfunc

    receivables = db.query(Receivable).filter(
        Receivable.tenant_id == tenant_id,
        Receivable.status.in_(["unpaid", "partial"]),
    ).all()

    payables = db.query(Payable).filter(
        Payable.tenant_id == tenant_id,
        Payable.status.in_(["unpaid", "partial"]),
    ).all()

    today = date.today()
    return {
        "total_receivable": sum(r.amount - r.paid_amount for r in receivables),
        "total_payable": sum(p.amount - p.paid_amount for p in payables),
        "receivable_count": len(receivables),
        "payable_count": len(payables),
        "overdue_receivable": sum(1 for r in receivables if r.due_date and r.due_date < today),
        "overdue_payable": sum(1 for p in payables if p.due_date and p.due_date < today),
    }
