"""Sales Order web routes — list, create, view, lines, confirm/ship/complete + quotation conversion."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User, Customer, Item, Quotation
from src.routes.web import require_login, templates, ctx, add_flash
from src.services import sales_service

router = APIRouter(prefix="/web/sales", tags=["sales"])


@router.get("")
def sales_list(
    request: Request,
    search: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """List all sales orders."""
    orders = sales_service.list_sales_orders(db, user.tenant_id, search, status)
    return templates.TemplateResponse(
        "sales.html",
        ctx(request, user, orders=orders, search=search, status=status,
            total=len(orders), active_page="sales"),
    )


@router.get("/new")
def sales_new_form(
    request: Request,
    from_quotation: int = Query(0),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """New sales order form (or convert from quotation)."""
    # If from_quotation is provided, convert directly
    if from_quotation:
        so = sales_service.create_from_quotation(db, user.tenant_id, user.id, from_quotation)
        if so:
            add_flash(request, "success", f"已從報價單轉入銷貨單 {so.order_no}")
            return RedirectResponse(f"/web/sales/{so.id}", status_code=303)
        else:
            add_flash(request, "danger", "報價單轉入失敗（可能不存在或非已接受狀態）")
            return RedirectResponse("/web/quotations", status_code=303)

    customers = db.query(Customer).filter(
        Customer.tenant_id == user.tenant_id
    ).order_by(Customer.name).all()
    return templates.TemplateResponse(
        "sales_form.html",
        ctx(request, user, customers=customers, active_page="sales"),
    )


@router.post("/new")
def sales_create(
    request: Request,
    customer_id: int = Form(...),
    order_date: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Create a new sales order."""
    od = date.fromisoformat(order_date) if order_date else None
    so = sales_service.create_sales_order(
        db, user.tenant_id, user.id, customer_id, od, notes=notes
    )
    add_flash(request, "success", f"銷貨單 {so.order_no} 已建立")
    return RedirectResponse(f"/web/sales/{so.id}", status_code=303)


@router.get("/{order_id}")
def sales_detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """View sales order detail with lines."""
    so = sales_service.get_sales_order(db, order_id, user.tenant_id)
    if not so:
        add_flash(request, "danger", "銷貨單不存在")
        return RedirectResponse("/web/sales", status_code=303)

    items = db.query(Item).filter(
        Item.tenant_id == user.tenant_id
    ).order_by(Item.name).all()

    return templates.TemplateResponse(
        "sales_detail.html",
        ctx(request, user, so=so, items=items, active_page="sales"),
    )


@router.post("/{order_id}/lines/add")
def sales_add_line(
    order_id: int,
    request: Request,
    item_id: int = Form(...),
    quantity: int = Form(1),
    unit_price: str = Form("0"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Add a line item to sales order."""
    price = Decimal(unit_price) if unit_price else Decimal("0")
    line = sales_service.add_line(db, order_id, user.tenant_id, item_id, quantity, price, notes)
    if not line:
        add_flash(request, "danger", "無法新增明細（單據不存在或非草稿狀態）")
    return RedirectResponse(f"/web/sales/{order_id}", status_code=303)


@router.post("/{order_id}/lines/{line_id}/delete")
def sales_remove_line(
    order_id: int,
    line_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Remove a line from sales order."""
    success = sales_service.remove_line(db, line_id, order_id, user.tenant_id)
    if not success:
        add_flash(request, "danger", "無法刪除明細")
    return RedirectResponse(f"/web/sales/{order_id}", status_code=303)


@router.post("/{order_id}/confirm")
def sales_confirm(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Confirm a sales order."""
    so = sales_service.confirm_order(db, order_id, user.tenant_id)
    if not so:
        add_flash(request, "danger", "無法確認（無明細或非草稿狀態）")
    else:
        add_flash(request, "success", f"銷貨單 {so.order_no} 已確認")
    return RedirectResponse(f"/web/sales/{order_id}", status_code=303)


@router.post("/{order_id}/ship")
def sales_ship(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Mark sales order as shipped (triggers inventory deduction)."""
    from src.services.inventory_service import process_sales_ship
    so = sales_service.ship_order(db, order_id, user.tenant_id)
    if not so:
        add_flash(request, "danger", "無法出貨（非已確認狀態）")
    else:
        process_sales_ship(db, so, user.id)
        add_flash(request, "success", f"銷貨單 {so.order_no} 已出貨扣庫")
    return RedirectResponse(f"/web/sales/{order_id}", status_code=303)


@router.post("/{order_id}/complete")
def sales_complete(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Mark sales order as completed."""
    so = sales_service.complete_order(db, order_id, user.tenant_id)
    if not so:
        add_flash(request, "danger", "無法完成（非已出貨狀態）")
    else:
        add_flash(request, "success", f"銷貨單 {so.order_no} 已完成")
    return RedirectResponse(f"/web/sales/{order_id}", status_code=303)


@router.post("/{order_id}/cancel")
def sales_cancel(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Cancel a sales order."""
    so = sales_service.cancel_order(db, order_id, user.tenant_id)
    if not so:
        add_flash(request, "danger", "無法取消")
    else:
        add_flash(request, "warning", f"銷貨單 {so.order_no} 已取消")
    return RedirectResponse(f"/web/sales/{order_id}", status_code=303)


@router.post("/{order_id}/delete")
def sales_delete(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Delete a draft sales order."""
    success = sales_service.delete_order(db, order_id, user.tenant_id)
    if not success:
        add_flash(request, "danger", "無法刪除（僅草稿可刪除）")
        return RedirectResponse(f"/web/sales/{order_id}", status_code=303)
    add_flash(request, "success", "銷貨單已刪除")
    return RedirectResponse("/web/sales", status_code=303)
