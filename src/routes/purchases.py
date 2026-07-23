"""Purchase Order web routes — list, create, view, add/remove lines, confirm/receive."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User, Supplier, Item, PurchaseOrder
from src.routes.web import require_login, templates, ctx, add_flash
from src.services import purchase_service

router = APIRouter(prefix="/web/purchases", tags=["purchases"])


@router.get("")
def purchase_list(
    request: Request,
    search: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """List all purchase orders."""
    orders = purchase_service.list_purchase_orders(db, user.tenant_id, search, status)
    return templates.TemplateResponse(
        "purchases.html",
        ctx(request, user, orders=orders, search=search, status=status,
            total=len(orders), active_page="purchases"),
    )


@router.get("/new")
def purchase_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """New purchase order form."""
    suppliers = db.query(Supplier).filter(
        Supplier.tenant_id == user.tenant_id
    ).order_by(Supplier.name).all()
    return templates.TemplateResponse(
        "purchase_form.html",
        ctx(request, user, suppliers=suppliers, active_page="purchases"),
    )


@router.post("/new")
def purchase_create(
    request: Request,
    supplier_id: int = Form(...),
    order_date: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Create a new purchase order."""
    od = date.fromisoformat(order_date) if order_date else None
    po = purchase_service.create_purchase_order(
        db, user.tenant_id, user.id, supplier_id, od, notes
    )
    add_flash(request, "success", f"進貨單 {po.order_no} 已建立")
    return RedirectResponse(f"/web/purchases/{po.id}", status_code=303)


@router.get("/{order_id}")
def purchase_detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """View purchase order detail with lines."""
    po = purchase_service.get_purchase_order(db, order_id, user.tenant_id)
    if not po:
        add_flash(request, "danger", "進貨單不存在")
        return RedirectResponse("/web/purchases", status_code=303)

    items = db.query(Item).filter(
        Item.tenant_id == user.tenant_id
    ).order_by(Item.name).all()

    return templates.TemplateResponse(
        "purchase_detail.html",
        ctx(request, user, po=po, items=items, active_page="purchases"),
    )


@router.post("/{order_id}/lines/add")
def purchase_add_line(
    order_id: int,
    request: Request,
    item_id: int = Form(...),
    quantity: int = Form(1),
    unit_price: str = Form("0"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Add a line item to purchase order."""
    price = Decimal(unit_price) if unit_price else Decimal("0")
    line = purchase_service.add_line(db, order_id, user.tenant_id, item_id, quantity, price, notes)
    if not line:
        add_flash(request, "danger", "無法新增明細（單據不存在或非草稿狀態）")
    return RedirectResponse(f"/web/purchases/{order_id}", status_code=303)


@router.post("/{order_id}/lines/{line_id}/delete")
def purchase_remove_line(
    order_id: int,
    line_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Remove a line from purchase order."""
    success = purchase_service.remove_line(db, line_id, order_id, user.tenant_id)
    if not success:
        add_flash(request, "danger", "無法刪除明細")
    return RedirectResponse(f"/web/purchases/{order_id}", status_code=303)


@router.post("/{order_id}/confirm")
def purchase_confirm(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Confirm a purchase order."""
    po = purchase_service.confirm_order(db, order_id, user.tenant_id)
    if not po:
        add_flash(request, "danger", "無法確認（單據不存在、無明細或非草稿狀態）")
    else:
        add_flash(request, "success", f"進貨單 {po.order_no} 已確認")
    return RedirectResponse(f"/web/purchases/{order_id}", status_code=303)


@router.post("/{order_id}/receive")
def purchase_receive(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Mark purchase order as received (triggers inventory update)."""
    from src.services.inventory_service import process_purchase_receive
    po = purchase_service.receive_order(db, order_id, user.tenant_id)
    if not po:
        add_flash(request, "danger", "無法收貨（非已確認狀態）")
    else:
        process_purchase_receive(db, po, user.id)
        add_flash(request, "success", f"進貨單 {po.order_no} 已收貨入庫")
    return RedirectResponse(f"/web/purchases/{order_id}", status_code=303)


@router.post("/{order_id}/cancel")
def purchase_cancel(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Cancel a purchase order."""
    po = purchase_service.cancel_order(db, order_id, user.tenant_id)
    if not po:
        add_flash(request, "danger", "無法取消")
    else:
        add_flash(request, "warning", f"進貨單 {po.order_no} 已取消")
    return RedirectResponse(f"/web/purchases/{order_id}", status_code=303)


@router.post("/{order_id}/delete")
def purchase_delete(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Delete a draft purchase order."""
    success = purchase_service.delete_order(db, order_id, user.tenant_id)
    if not success:
        add_flash(request, "danger", "無法刪除（僅草稿可刪除）")
        return RedirectResponse(f"/web/purchases/{order_id}", status_code=303)
    add_flash(request, "success", "進貨單已刪除")
    return RedirectResponse("/web/purchases", status_code=303)
