"""Repair Order web routes — list, create, view, parts, status transitions."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User, Customer, Item
from src.routes.web import require_login, templates, ctx, add_flash
from src.services import repair_service

router = APIRouter(prefix="/web/repairs", tags=["repairs"])

STATUS_LABELS = {
    "received": "已收件",
    "diagnosing": "檢測中",
    "repairing": "維修中",
    "waiting_parts": "等零件",
    "done": "已完工",
    "returned": "已取件",
}


@router.get("")
def repair_list(
    request: Request,
    search: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    orders = repair_service.list_repair_orders(db, user.tenant_id, search, status)
    return templates.TemplateResponse(
        "repairs.html",
        ctx(request, user, orders=orders, search=search, status=status,
            total=len(orders), status_labels=STATUS_LABELS, active_page="repairs"),
    )


@router.get("/new")
def repair_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    customers = db.query(Customer).filter(
        Customer.tenant_id == user.tenant_id
    ).order_by(Customer.name).all()
    return templates.TemplateResponse(
        "repair_form.html",
        ctx(request, user, customers=customers, active_page="repairs"),
    )


@router.post("/new")
def repair_create(
    request: Request,
    customer_id: int = Form(...),
    item_name: str = Form(...),
    fault_desc: str = Form(...),
    brand: str = Form(""),
    model: str = Form(""),
    serial_no: str = Form(""),
    warranty_until: str = Form(""),
    received_date: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    wu = date.fromisoformat(warranty_until) if warranty_until else None
    rd = date.fromisoformat(received_date) if received_date else None
    ro = repair_service.create_repair_order(
        db, user.tenant_id, user.id,
        customer_id, item_name, fault_desc,
        brand, model, serial_no, wu, rd,
    )
    add_flash(request, "success", f"維修單 {ro.repair_no} 已建立")
    return RedirectResponse(f"/web/repairs/{ro.id}", status_code=303)


@router.get("/{order_id}")
def repair_detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    ro = repair_service.get_repair_order(db, order_id, user.tenant_id)
    if not ro:
        add_flash(request, "danger", "維修單不存在")
        return RedirectResponse("/web/repairs", status_code=303)

    items = db.query(Item).filter(
        Item.tenant_id == user.tenant_id
    ).order_by(Item.name).all()

    valid_transitions = repair_service.VALID_TRANSITIONS.get(ro.status, [])
    return templates.TemplateResponse(
        "repair_detail.html",
        ctx(request, user, ro=ro, items=items, valid_transitions=valid_transitions,
            status_labels=STATUS_LABELS, active_page="repairs"),
    )


@router.post("/{order_id}/status")
def repair_status_update(
    order_id: int,
    request: Request,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    ro = repair_service.update_status(db, order_id, user.tenant_id, new_status)
    if not ro:
        add_flash(request, "danger", "狀態轉換失敗")
    else:
        add_flash(request, "success", f"狀態已更新為「{STATUS_LABELS.get(new_status, new_status)}」")
    return RedirectResponse(f"/web/repairs/{order_id}", status_code=303)


@router.post("/{order_id}/details")
def repair_update_details(
    order_id: int,
    request: Request,
    repair_desc: str = Form(""),
    labor_fee: str = Form("0"),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    lf = Decimal(labor_fee) if labor_fee else Decimal("0")
    ro = repair_service.update_repair_details(db, order_id, user.tenant_id, repair_desc, lf)
    if not ro:
        add_flash(request, "danger", "更新失敗")
    else:
        add_flash(request, "success", "維修內容已更新")
    return RedirectResponse(f"/web/repairs/{order_id}", status_code=303)


@router.post("/{order_id}/parts/add")
def repair_add_part(
    order_id: int,
    request: Request,
    part_name: str = Form(...),
    quantity: int = Form(1),
    unit_price: str = Form("0"),
    item_id: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    price = Decimal(unit_price) if unit_price else Decimal("0")
    iid = int(item_id) if item_id else None
    part = repair_service.add_part(db, order_id, user.tenant_id, part_name, quantity, price, iid, notes)
    if not part:
        add_flash(request, "danger", "無法新增零件")
    return RedirectResponse(f"/web/repairs/{order_id}", status_code=303)


@router.post("/{order_id}/parts/{part_id}/delete")
def repair_remove_part(
    order_id: int,
    part_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    repair_service.remove_part(db, part_id, order_id, user.tenant_id)
    return RedirectResponse(f"/web/repairs/{order_id}", status_code=303)
