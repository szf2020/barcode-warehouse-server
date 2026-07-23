"""Accounting web routes — receivables, payables, payments, summary."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User
from src.routes.web import require_login, templates, ctx, add_flash
from src.services import accounting_service

router = APIRouter(prefix="/web/accounting", tags=["accounting"])


@router.get("")
def accounting_summary(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Accounting summary dashboard."""
    summary = accounting_service.get_summary(db, user.tenant_id)
    return templates.TemplateResponse(
        "accounting.html",
        ctx(request, user, summary=summary, active_page="accounting"),
    )


@router.get("/receivables")
def receivable_list(
    request: Request,
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """List receivables."""
    items = accounting_service.list_receivables(db, user.tenant_id, status)
    return templates.TemplateResponse(
        "receivables.html",
        ctx(request, user, items=items, status=status,
            total=len(items), active_page="accounting"),
    )


@router.post("/receivables/{rec_id}/pay")
def receivable_pay(
    rec_id: int,
    request: Request,
    amount: str = Form(...),
    payment_method: str = Form("cash"),
    payment_date: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Record a payment received."""
    amt = Decimal(amount)
    pd = date.fromisoformat(payment_date) if payment_date else None
    payment = accounting_service.record_receive_payment(
        db, rec_id, user.tenant_id, user.id, amt, payment_method, pd, notes
    )
    if not payment:
        add_flash(request, "danger", "收款失敗（帳款不存在或已結清）")
    else:
        add_flash(request, "success", f"已收款 ${amt:,.0f}")
    return RedirectResponse("/web/accounting/receivables", status_code=303)


@router.get("/payables")
def payable_list(
    request: Request,
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """List payables."""
    items = accounting_service.list_payables(db, user.tenant_id, status)
    return templates.TemplateResponse(
        "payables.html",
        ctx(request, user, items=items, status=status,
            total=len(items), active_page="accounting"),
    )


@router.post("/payables/{pay_id}/pay")
def payable_pay(
    pay_id: int,
    request: Request,
    amount: str = Form(...),
    payment_method: str = Form("cash"),
    payment_date: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Record a payment made."""
    amt = Decimal(amount)
    pd = date.fromisoformat(payment_date) if payment_date else None
    payment = accounting_service.record_pay_payment(
        db, pay_id, user.tenant_id, user.id, amt, payment_method, pd, notes
    )
    if not payment:
        add_flash(request, "danger", "付款失敗（帳款不存在或已結清）")
    else:
        add_flash(request, "success", f"已付款 ${amt:,.0f}")
    return RedirectResponse("/web/accounting/payables", status_code=303)
