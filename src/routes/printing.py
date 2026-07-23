"""Printing routes — trigger document printing via API."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User
from src.routes.web import require_login, add_flash
from src.printing.printer import printer, PrinterError
from src.services import purchase_service, sales_service, quotation_service, repair_service

router = APIRouter(prefix="/api/print", tags=["printing"])


@router.post("/purchase/{order_id}")
def print_purchase_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Print a purchase order."""
    from src.printing.templates.purchase_order import render_purchase_order

    po = purchase_service.get_purchase_order(db, order_id, user.tenant_id)
    if not po:
        return JSONResponse({"error": "進貨單不存在"}, status_code=404)

    data = render_purchase_order(po)
    return _send_to_printer(request, data, f"進貨單 {po.order_no}", f"/web/purchases/{order_id}")


@router.post("/sales/{order_id}")
def print_sales_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Print a sales order."""
    from src.printing.templates.sales_order import render_sales_order

    so = sales_service.get_sales_order(db, order_id, user.tenant_id)
    if not so:
        return JSONResponse({"error": "銷貨單不存在"}, status_code=404)

    data = render_sales_order(so)
    return _send_to_printer(request, data, f"銷貨單 {so.order_no}", f"/web/sales/{order_id}")


@router.post("/quotation/{quotation_id}")
def print_quotation(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Print a quotation."""
    from src.printing.templates.sales_order import render_quotation

    qt = quotation_service.get_quotation(db, quotation_id, user.tenant_id)
    if not qt:
        return JSONResponse({"error": "報價單不存在"}, status_code=404)

    data = render_quotation(qt)
    return _send_to_printer(request, data, f"報價單 {qt.quote_no}", f"/web/quotations/{quotation_id}")


@router.post("/repair/{order_id}/receipt")
def print_repair_receipt(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Print a repair receipt (收件單)."""
    from src.printing.templates.repair_order import render_repair_receipt

    ro = repair_service.get_repair_order(db, order_id, user.tenant_id)
    if not ro:
        return JSONResponse({"error": "維修單不存在"}, status_code=404)

    data = render_repair_receipt(ro)
    return _send_to_printer(request, data, f"收件單 {ro.repair_no}", f"/web/repairs/{order_id}")


@router.post("/repair/{order_id}/completion")
def print_repair_completion(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Print a repair completion notice (完工單)."""
    from src.printing.templates.repair_order import render_repair_completion

    ro = repair_service.get_repair_order(db, order_id, user.tenant_id)
    if not ro:
        return JSONResponse({"error": "維修單不存在"}, status_code=404)

    data = render_repair_completion(ro)
    return _send_to_printer(request, data, f"完工單 {ro.repair_no}", f"/web/repairs/{order_id}")


def _send_to_printer(request: Request, data: bytes, doc_name: str, redirect_url: str):
    """Send data to printer with fallback to file."""
    try:
        if printer.is_available():
            printer.print_raw(data)
            add_flash(request, "success", f"{doc_name} 已送出列印")
        else:
            # Fallback: save to file
            path = printer.print_to_file(data)
            add_flash(request, "warning", f"{doc_name} 印表機不可用，已儲存至 {path}")
    except PrinterError as e:
        add_flash(request, "danger", f"列印失敗：{e}")

    return RedirectResponse(redirect_url, status_code=303)
