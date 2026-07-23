"""Quotation web routes — list, create, view, add/remove lines, send/accept/reject."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User, Customer, Item
from src.routes.web import require_login, templates, ctx, add_flash
from src.services import quotation_service

router = APIRouter(prefix="/web/quotations", tags=["quotations"])


@router.get("")
def quotation_list(
    request: Request,
    search: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """List all quotations."""
    quotes = quotation_service.list_quotations(db, user.tenant_id, search, status)
    return templates.TemplateResponse(
        "quotations.html",
        ctx(request, user, quotes=quotes, search=search, status=status,
            total=len(quotes), active_page="quotations"),
    )


@router.get("/new")
def quotation_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """New quotation form."""
    customers = db.query(Customer).filter(
        Customer.tenant_id == user.tenant_id
    ).order_by(Customer.name).all()
    return templates.TemplateResponse(
        "quotation_form.html",
        ctx(request, user, customers=customers, active_page="quotations"),
    )


@router.post("/new")
def quotation_create(
    request: Request,
    customer_id: int = Form(...),
    quote_date: str = Form(""),
    valid_until: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Create a new quotation."""
    qd = date.fromisoformat(quote_date) if quote_date else None
    vu = date.fromisoformat(valid_until) if valid_until else None
    qt = quotation_service.create_quotation(
        db, user.tenant_id, user.id, customer_id, qd, vu, notes
    )
    add_flash(request, "success", f"報價單 {qt.quote_no} 已建立")
    return RedirectResponse(f"/web/quotations/{qt.id}", status_code=303)


@router.get("/{quotation_id}")
def quotation_detail(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """View quotation detail with lines."""
    qt = quotation_service.get_quotation(db, quotation_id, user.tenant_id)
    if not qt:
        add_flash(request, "danger", "報價單不存在")
        return RedirectResponse("/web/quotations", status_code=303)

    items = db.query(Item).filter(
        Item.tenant_id == user.tenant_id
    ).order_by(Item.name).all()

    return templates.TemplateResponse(
        "quotation_detail.html",
        ctx(request, user, qt=qt, items=items, active_page="quotations"),
    )


@router.post("/{quotation_id}/lines/add")
def quotation_add_line(
    quotation_id: int,
    request: Request,
    item_id: int = Form(...),
    quantity: int = Form(1),
    unit_price: str = Form("0"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Add a line item to quotation."""
    price = Decimal(unit_price) if unit_price else Decimal("0")
    line = quotation_service.add_line(db, quotation_id, user.tenant_id, item_id, quantity, price, notes)
    if not line:
        add_flash(request, "danger", "無法新增明細（單據不存在或非草稿狀態）")
    return RedirectResponse(f"/web/quotations/{quotation_id}", status_code=303)


@router.post("/{quotation_id}/lines/{line_id}/delete")
def quotation_remove_line(
    quotation_id: int,
    line_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Remove a line from quotation."""
    success = quotation_service.remove_line(db, line_id, quotation_id, user.tenant_id)
    if not success:
        add_flash(request, "danger", "無法刪除明細")
    return RedirectResponse(f"/web/quotations/{quotation_id}", status_code=303)


@router.post("/{quotation_id}/send")
def quotation_send(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Send quotation to customer."""
    qt = quotation_service.send_quotation(db, quotation_id, user.tenant_id)
    if not qt:
        add_flash(request, "danger", "無法送出（無明細或非草稿狀態）")
    else:
        add_flash(request, "success", f"報價單 {qt.quote_no} 已送出")
    return RedirectResponse(f"/web/quotations/{quotation_id}", status_code=303)


@router.post("/{quotation_id}/accept")
def quotation_accept(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Mark quotation as accepted."""
    qt = quotation_service.accept_quotation(db, quotation_id, user.tenant_id)
    if not qt:
        add_flash(request, "danger", "無法接受")
    else:
        add_flash(request, "success", f"報價單 {qt.quote_no} 已接受，可轉為銷貨單")
    return RedirectResponse(f"/web/quotations/{quotation_id}", status_code=303)


@router.post("/{quotation_id}/reject")
def quotation_reject(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Reject a quotation."""
    qt = quotation_service.reject_quotation(db, quotation_id, user.tenant_id)
    if not qt:
        add_flash(request, "danger", "無法拒絕")
    else:
        add_flash(request, "warning", f"報價單 {qt.quote_no} 已拒絕")
    return RedirectResponse(f"/web/quotations/{quotation_id}", status_code=303)


@router.post("/{quotation_id}/delete")
def quotation_delete(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Delete a draft quotation."""
    success = quotation_service.delete_quotation(db, quotation_id, user.tenant_id)
    if not success:
        add_flash(request, "danger", "無法刪除（僅草稿可刪除）")
        return RedirectResponse(f"/web/quotations/{quotation_id}", status_code=303)
    add_flash(request, "success", "報價單已刪除")
    return RedirectResponse("/web/quotations", status_code=303)
