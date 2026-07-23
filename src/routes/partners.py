"""Partner management routes — Customers & Suppliers CRUD with Web UI."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from src.database import get_db
from src.models import User, Customer, Supplier
from src.routes.web import require_login, templates, ctx, add_flash

router = APIRouter(prefix="/web", tags=["partners"])


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/customers")
def customer_list(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """List all customers for current tenant."""
    query = db.query(Customer).filter(Customer.tenant_id == user.tenant_id)
    if search:
        query = query.filter(
            or_(
                Customer.code.ilike(f"%{search}%"),
                Customer.name.ilike(f"%{search}%"),
                Customer.phone.ilike(f"%{search}%"),
                Customer.contact_person.ilike(f"%{search}%"),
            )
        )
    customers = query.order_by(Customer.code).all()
    return templates.TemplateResponse(
        "customers.html",
        ctx(request, user, customers=customers, search=search,
            total=len(customers), active_page="customers"),
    )


@router.get("/customers/new")
def customer_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """New customer form."""
    return templates.TemplateResponse(
        "customer_form.html",
        ctx(request, user, customer=None, active_page="customers"),
    )


@router.post("/customers/new")
def customer_create(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    contact_person: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    tax_id: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Create a new customer."""
    # Check duplicates
    existing = db.query(Customer).filter(
        Customer.code == code, Customer.tenant_id == user.tenant_id
    ).first()
    if existing:
        add_flash(request, "danger", f"客戶編號 {code} 已存在")
        return RedirectResponse("/web/customers/new", status_code=303)

    customer = Customer(
        code=code,
        name=name,
        contact_person=contact_person or None,
        phone=phone or None,
        address=address or None,
        tax_id=tax_id or None,
        notes=notes or None,
        tenant_id=user.tenant_id,
    )
    db.add(customer)
    db.commit()
    add_flash(request, "success", f"客戶 {name} 已建立")
    return RedirectResponse("/web/customers", status_code=303)


@router.get("/customers/{customer_id}/edit")
def customer_edit_form(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Edit customer form."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id, Customer.tenant_id == user.tenant_id
    ).first()
    if not customer:
        add_flash(request, "danger", "客戶不存在")
        return RedirectResponse("/web/customers", status_code=303)
    return templates.TemplateResponse(
        "customer_form.html",
        ctx(request, user, customer=customer, active_page="customers"),
    )


@router.post("/customers/{customer_id}/edit")
def customer_update(
    customer_id: int,
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    contact_person: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    tax_id: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Update a customer."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id, Customer.tenant_id == user.tenant_id
    ).first()
    if not customer:
        add_flash(request, "danger", "客戶不存在")
        return RedirectResponse("/web/customers", status_code=303)

    # Check code conflict
    conflict = db.query(Customer).filter(
        Customer.code == code,
        Customer.tenant_id == user.tenant_id,
        Customer.id != customer_id,
    ).first()
    if conflict:
        add_flash(request, "danger", f"客戶編號 {code} 已被其他客戶使用")
        return RedirectResponse(f"/web/customers/{customer_id}/edit", status_code=303)

    customer.code = code
    customer.name = name
    customer.contact_person = contact_person or None
    customer.phone = phone or None
    customer.address = address or None
    customer.tax_id = tax_id or None
    customer.notes = notes or None
    db.commit()
    add_flash(request, "success", f"客戶 {name} 已更新")
    return RedirectResponse("/web/customers", status_code=303)


@router.post("/customers/{customer_id}/delete")
def customer_delete(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Delete a customer."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id, Customer.tenant_id == user.tenant_id
    ).first()
    if not customer:
        add_flash(request, "danger", "客戶不存在")
    else:
        db.delete(customer)
        db.commit()
        add_flash(request, "success", f"客戶 {customer.name} 已刪除")
    return RedirectResponse("/web/customers", status_code=303)


# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/suppliers")
def supplier_list(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """List all suppliers for current tenant."""
    query = db.query(Supplier).filter(Supplier.tenant_id == user.tenant_id)
    if search:
        query = query.filter(
            or_(
                Supplier.code.ilike(f"%{search}%"),
                Supplier.name.ilike(f"%{search}%"),
                Supplier.phone.ilike(f"%{search}%"),
                Supplier.contact_person.ilike(f"%{search}%"),
            )
        )
    suppliers = query.order_by(Supplier.code).all()
    return templates.TemplateResponse(
        "suppliers.html",
        ctx(request, user, suppliers=suppliers, search=search,
            total=len(suppliers), active_page="suppliers"),
    )


@router.get("/suppliers/new")
def supplier_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """New supplier form."""
    return templates.TemplateResponse(
        "supplier_form.html",
        ctx(request, user, supplier=None, active_page="suppliers"),
    )


@router.post("/suppliers/new")
def supplier_create(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    contact_person: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    tax_id: str = Form(""),
    bank_account: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Create a new supplier."""
    existing = db.query(Supplier).filter(
        Supplier.code == code, Supplier.tenant_id == user.tenant_id
    ).first()
    if existing:
        add_flash(request, "danger", f"供應商編號 {code} 已存在")
        return RedirectResponse("/web/suppliers/new", status_code=303)

    supplier = Supplier(
        code=code,
        name=name,
        contact_person=contact_person or None,
        phone=phone or None,
        address=address or None,
        tax_id=tax_id or None,
        bank_account=bank_account or None,
        notes=notes or None,
        tenant_id=user.tenant_id,
    )
    db.add(supplier)
    db.commit()
    add_flash(request, "success", f"供應商 {name} 已建立")
    return RedirectResponse("/web/suppliers", status_code=303)


@router.get("/suppliers/{supplier_id}/edit")
def supplier_edit_form(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Edit supplier form."""
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.tenant_id == user.tenant_id
    ).first()
    if not supplier:
        add_flash(request, "danger", "供應商不存在")
        return RedirectResponse("/web/suppliers", status_code=303)
    return templates.TemplateResponse(
        "supplier_form.html",
        ctx(request, user, supplier=supplier, active_page="suppliers"),
    )


@router.post("/suppliers/{supplier_id}/edit")
def supplier_update(
    supplier_id: int,
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    contact_person: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    tax_id: str = Form(""),
    bank_account: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Update a supplier."""
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.tenant_id == user.tenant_id
    ).first()
    if not supplier:
        add_flash(request, "danger", "供應商不存在")
        return RedirectResponse("/web/suppliers", status_code=303)

    conflict = db.query(Supplier).filter(
        Supplier.code == code,
        Supplier.tenant_id == user.tenant_id,
        Supplier.id != supplier_id,
    ).first()
    if conflict:
        add_flash(request, "danger", f"供應商編號 {code} 已被其他供應商使用")
        return RedirectResponse(f"/web/suppliers/{supplier_id}/edit", status_code=303)

    supplier.code = code
    supplier.name = name
    supplier.contact_person = contact_person or None
    supplier.phone = phone or None
    supplier.address = address or None
    supplier.tax_id = tax_id or None
    supplier.bank_account = bank_account or None
    supplier.notes = notes or None
    db.commit()
    add_flash(request, "success", f"供應商 {name} 已更新")
    return RedirectResponse("/web/suppliers", status_code=303)


@router.post("/suppliers/{supplier_id}/delete")
def supplier_delete(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Delete a supplier."""
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.tenant_id == user.tenant_id
    ).first()
    if not supplier:
        add_flash(request, "danger", "供應商不存在")
    else:
        db.delete(supplier)
        db.commit()
        add_flash(request, "success", f"供應商 {supplier.name} 已刪除")
    return RedirectResponse("/web/suppliers", status_code=303)
