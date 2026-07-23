"""Seed script — Create initial super_admin account and default tenant."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import SessionLocal, init_db
from src.models import Tenant, User
from src.services.auth_service import hash_password


def seed():
    """Create initial data: default tenant + super_admin account."""
    print("Initializing database tables...")
    init_db()

    db = SessionLocal()
    try:
        # Create default tenant if not exists
        default_tenant = db.query(Tenant).filter(Tenant.code == "DEFAULT").first()
        if not default_tenant:
            default_tenant = Tenant(name="預設廠商", code="DEFAULT")
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
            print(f"✓ 建立預設廠商: {default_tenant.name} (code: {default_tenant.code})")
        else:
            print(f"⊘ 預設廠商已存在: {default_tenant.name}")

        # Create super_admin if not exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                display_name="系統管理員",
                role="super_admin",
                tenant_id=default_tenant.id,
            )
            db.add(admin)
            db.commit()
            print(f"✓ 建立超級管理員帳號:")
            print(f"  帳號: admin")
            print(f"  密碼: admin123")
            print(f"  ⚠️  請登入後立即修改密碼！")
        else:
            print(f"⊘ 管理員帳號已存在: {admin.username}")

    finally:
        db.close()

    print("\nSeed 完成！")
    print(f"前端網址: http://localhost:8000/web/login")


if __name__ == "__main__":
    seed()
