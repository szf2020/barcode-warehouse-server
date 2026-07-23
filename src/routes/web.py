"""Web frontend routes — Jinja2 template rendering with authentication."""

from pathlib import Path
from typing import Optional
from functools import wraps

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User, Item, Tenant
from src.services.auth_service import authenticate_user, get_user_by_id

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web", tags=["web"])


# ─── Auth Helpers ────────────────────────────────────────────────────────────

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user from session. Returns None if not logged in."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(db, user_id)


def require_login(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency that requires login. Redirects to login page if not authenticated."""
    user = get_current_user(request, db)
    if not user:
        # Store the target URL to redirect after login
        raise RedirectToLogin()
    return user


class RedirectToLogin(Exception):
    """Exception raised to redirect to login page."""
    pass


# ─── Exception Handler (registered in main.py) ──────────────────────────────

def add_flash(request: Request, category: str, message: str):
    """Add a flash message to the session."""
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append([category, message])


def get_flashed_messages(request: Request) -> list:
    """Get and clear flash messages from session."""
    messages = request.session.pop("_messages", [])
    return messages


# ─── Template context helper ─────────────────────────────────────────────────

def ctx(request: Request, user: Optional[User] = None, **kwargs) -> dict:
    """Build template context with common variables."""
    context = {
        "request": request,
        "user": user,
        "get_flashed_messages": lambda: get_flashed_messages(request),
    }
    context.update(kwargs)
    return context


# ─── Auth Routes ─────────────────────────────────────────────────────────────

@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    """Login page."""
    # If already logged in, redirect to items
    user_id = request.session.get("user_id")
    if user_id:
        user = get_user_by_id(db, user_id)
        if user:
            return RedirectResponse(url="/web/items", status_code=302)
        # Invalid session (user no longer exists) — clear it
        request.session.clear()
    return templates.TemplateResponse("login.html", ctx(request))


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle login form submission."""
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            ctx(request, error="帳號或密碼錯誤"),
            status_code=401,
        )

    # Set session
    request.session["user_id"] = user.id
    add_flash(request, "success", f"歡迎回來，{user.display_name}！")
    return RedirectResponse(url="/web/items", status_code=302)


@router.post("/logout")
def logout(request: Request):
    """Handle logout."""
    request.session.clear()
    return RedirectResponse(url="/web/login", status_code=302)


# ─── Items Routes ────────────────────────────────────────────────────────────

@router.get("/items")
def items_list(
    request: Request,
    search: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
):
    """Items list page with search and pagination."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/web/login", status_code=302)

    page_size = 20
    query = db.query(Item)

    # Tenant isolation: non-super_admin only sees own tenant's items
    if user.role != "super_admin":
        query = query.filter(Item.tenant_id == user.tenant_id)

    # Search
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Item.barcode.ilike(search_filter))
            | (Item.name.ilike(search_filter))
            | (Item.spec.ilike(search_filter))
            | (Item.location.ilike(search_filter))
            | (Item.supplier.ilike(search_filter))
        )

    # Count total
    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    # Paginate
    items = query.order_by(Item.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return templates.TemplateResponse("items.html", ctx(
        request, user=user,
        items=items,
        search=search,
        page=page,
        total_pages=total_pages,
        total=total,
        active_page="items",
    ))


@router.get("/items/new")
def item_new(request: Request, db: Session = Depends(get_db)):
    """New item form page."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/web/login", status_code=302)

    return templates.TemplateResponse("item_form.html", ctx(
        request, user=user,
        item=None,
        active_page="items",
    ))


@router.post("/items/new")
def item_create(
    request: Request,
    barcode: str = Form(...),
    name: str = Form(...),
    spec: str = Form(""),
    quantity: int = Form(0),
    location: str = Form(""),
    supplier: str = Form(""),
    db: Session = Depends(get_db),
):
    """Handle new item form submission."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/web/login", status_code=302)

    # Check duplicate barcode
    existing = db.query(Item).filter(Item.barcode == barcode).first()
    if existing:
        add_flash(request, "danger", f"條碼 '{barcode}' 已存在")
        return templates.TemplateResponse("item_form.html", ctx(
            request, user=user,
            item=None,
            active_page="items",
            form_data={"barcode": barcode, "name": name, "spec": spec,
                       "quantity": quantity, "location": location, "supplier": supplier},
        ))

    # Determine tenant_id
    tenant_id = user.tenant_id
    if user.role == "super_admin":
        # super_admin must specify or use a default tenant
        tenant_id = user.tenant_id or 1  # fallback

    new_item = Item(
        barcode=barcode,
        name=name,
        spec=spec or None,
        quantity=quantity,
        location=location or None,
        supplier=supplier or None,
        tenant_id=tenant_id,
    )
    db.add(new_item)
    db.commit()

    add_flash(request, "success", f"品項 '{name}' 已建立")
    return RedirectResponse(url="/web/items", status_code=302)


@router.get("/items/{barcode}/edit")
def item_edit(request: Request, barcode: str, db: Session = Depends(get_db)):
    """Edit item form page."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/web/login", status_code=302)

    item = db.query(Item).filter(Item.barcode == barcode).first()
    if not item:
        add_flash(request, "danger", "找不到此品項")
        return RedirectResponse(url="/web/items", status_code=302)

    # Tenant isolation
    if user.role != "super_admin" and item.tenant_id != user.tenant_id:
        add_flash(request, "danger", "無權限存取此品項")
        return RedirectResponse(url="/web/items", status_code=302)

    return templates.TemplateResponse("item_form.html", ctx(
        request, user=user,
        item=item,
        active_page="items",
    ))


@router.post("/items/{barcode}/edit")
def item_update(
    request: Request,
    barcode: str,
    name: str = Form(...),
    spec: str = Form(""),
    quantity: int = Form(0),
    location: str = Form(""),
    supplier: str = Form(""),
    db: Session = Depends(get_db),
):
    """Handle edit item form submission."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/web/login", status_code=302)

    item = db.query(Item).filter(Item.barcode == barcode).first()
    if not item:
        add_flash(request, "danger", "找不到此品項")
        return RedirectResponse(url="/web/items", status_code=302)

    # Tenant isolation
    if user.role != "super_admin" and item.tenant_id != user.tenant_id:
        add_flash(request, "danger", "無權限存取此品項")
        return RedirectResponse(url="/web/items", status_code=302)

    item.name = name
    item.spec = spec or None
    item.quantity = quantity
    item.location = location or None
    item.supplier = supplier or None
    db.commit()

    add_flash(request, "success", f"品項 '{name}' 已更新")
    return RedirectResponse(url="/web/items", status_code=302)


@router.post("/items/{barcode}/delete")
def item_delete(request: Request, barcode: str, db: Session = Depends(get_db)):
    """Handle item deletion."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/web/login", status_code=302)

    item = db.query(Item).filter(Item.barcode == barcode).first()
    if not item:
        add_flash(request, "danger", "找不到此品項")
        return RedirectResponse(url="/web/items", status_code=302)

    # Tenant isolation
    if user.role != "super_admin" and item.tenant_id != user.tenant_id:
        add_flash(request, "danger", "無權限刪除此品項")
        return RedirectResponse(url="/web/items", status_code=302)

    item_name = item.name
    db.delete(item)
    db.commit()

    add_flash(request, "success", f"品項 '{item_name}' 已刪除")
    return RedirectResponse(url="/web/items", status_code=302)


# ─── Tenants Routes (super_admin only) ───────────────────────────────────────

@router.get("/tenants")
def tenants_list(request: Request, db: Session = Depends(get_db)):
    """Tenants management page."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/web/login", status_code=302)
    if user.role != "super_admin":
        add_flash(request, "danger", "無權限存取")
        return RedirectResponse(url="/web/items", status_code=302)

    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    return templates.TemplateResponse("tenants.html", ctx(
        request, user=user,
        tenants=tenants,
        active_page="tenants",
    ))


@router.post("/tenants/new")
def tenant_create(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create a new tenant."""
    user = get_current_user(request, db)
    if not user or user.role != "super_admin":
        return RedirectResponse(url="/web/login", status_code=302)

    existing = db.query(Tenant).filter(Tenant.code == code).first()
    if existing:
        add_flash(request, "danger", f"廠商代碼 '{code}' 已存在")
        return RedirectResponse(url="/web/tenants", status_code=302)

    tenant = Tenant(name=name, code=code)
    db.add(tenant)
    db.commit()

    add_flash(request, "success", f"廠商 '{name}' 已建立")
    return RedirectResponse(url="/web/tenants", status_code=302)


@router.post("/tenants/{tenant_id}/toggle")
def tenant_toggle(request: Request, tenant_id: int, db: Session = Depends(get_db)):
    """Toggle tenant active status."""
    user = get_current_user(request, db)
    if not user or user.role != "super_admin":
        return RedirectResponse(url="/web/login", status_code=302)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant:
        tenant.is_active = not tenant.is_active
        db.commit()
        status = "啟用" if tenant.is_active else "停用"
        add_flash(request, "success", f"廠商 '{tenant.name}' 已{status}")

    return RedirectResponse(url="/web/tenants", status_code=302)


# ─── Users Routes (admin+) ───────────────────────────────────────────────────

@router.get("/users")
def users_list(request: Request, db: Session = Depends(get_db)):
    """Users management page."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/web/login", status_code=302)
    if user.role not in ["super_admin", "tenant_admin"]:
        add_flash(request, "danger", "無權限存取")
        return RedirectResponse(url="/web/items", status_code=302)

    query = db.query(User)
    if user.role == "tenant_admin":
        # tenant_admin only sees own tenant's users
        query = query.filter(User.tenant_id == user.tenant_id)

    users = query.order_by(User.created_at.desc()).all()
    tenants = db.query(Tenant).filter(Tenant.is_active == True).all() if user.role == "super_admin" else []

    return templates.TemplateResponse("users.html", ctx(
        request, user=user,
        users=users,
        tenants=tenants,
        active_page="users",
    ))


@router.post("/users/new")
def user_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
    role: str = Form("user"),
    tenant_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Create a new user."""
    from src.services.auth_service import hash_password

    user = get_current_user(request, db)
    if not user or user.role not in ["super_admin", "tenant_admin"]:
        return RedirectResponse(url="/web/login", status_code=302)

    # Tenant admin can only create users for own tenant
    if user.role == "tenant_admin":
        tenant_id = user.tenant_id
        if role not in ["user"]:
            role = "user"  # tenant_admin cannot create admins

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        add_flash(request, "danger", f"帳號 '{username}' 已存在")
        return RedirectResponse(url="/web/users", status_code=302)

    new_user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        tenant_id=tenant_id,
    )
    db.add(new_user)
    db.commit()

    add_flash(request, "success", f"帳號 '{username}' 已建立")
    return RedirectResponse(url="/web/users", status_code=302)


@router.post("/users/{user_id}/toggle")
def user_toggle(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Toggle user active status."""
    current_user = get_current_user(request, db)
    if not current_user or current_user.role not in ["super_admin", "tenant_admin"]:
        return RedirectResponse(url="/web/login", status_code=302)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        return RedirectResponse(url="/web/users", status_code=302)

    # Cannot disable yourself
    if target_user.id == current_user.id:
        add_flash(request, "danger", "無法停用自己的帳號")
        return RedirectResponse(url="/web/users", status_code=302)

    # Tenant admin can only manage own tenant's users
    if current_user.role == "tenant_admin" and target_user.tenant_id != current_user.tenant_id:
        add_flash(request, "danger", "無權限操作此帳號")
        return RedirectResponse(url="/web/users", status_code=302)

    target_user.is_active = not target_user.is_active
    db.commit()
    status = "啟用" if target_user.is_active else "停用"
    add_flash(request, "success", f"帳號 '{target_user.username}' 已{status}")

    return RedirectResponse(url="/web/users", status_code=302)


@router.post("/users/{user_id}/reset-password")
def user_reset_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Reset a user's password."""
    from src.services.auth_service import hash_password

    current_user = get_current_user(request, db)
    if not current_user or current_user.role not in ["super_admin", "tenant_admin"]:
        return RedirectResponse(url="/web/login", status_code=302)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        return RedirectResponse(url="/web/users", status_code=302)

    # Tenant admin can only manage own tenant's users
    if current_user.role == "tenant_admin" and target_user.tenant_id != current_user.tenant_id:
        add_flash(request, "danger", "無權限操作此帳號")
        return RedirectResponse(url="/web/users", status_code=302)

    target_user.password_hash = hash_password(new_password)
    db.commit()
    add_flash(request, "success", f"帳號 '{target_user.username}' 密碼已重設")

    return RedirectResponse(url="/web/users", status_code=302)
