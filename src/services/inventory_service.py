"""Inventory service — stock movement logic tied to order events.

- process_purchase_receive: 進貨收貨 → items qty 增加 + inventory_logs 記錄
- process_sales_ship: 銷貨出貨 → items qty 減少 + inventory_logs 記錄
"""

from sqlalchemy.orm import Session

from src.models.item import Item
from src.models.inventory import InventoryLog
from src.models.transaction import PurchaseOrder, SalesOrder


def process_purchase_receive(db: Session, po: PurchaseOrder, user_id: int = None):
    """Process inventory increase when a purchase order is received.

    For each line in the PO, increase item.quantity and write an inventory log.
    """
    for line in po.lines:
        item = db.query(Item).filter(Item.id == line.item_id).first()
        if not item:
            continue

        before_qty = item.quantity
        item.quantity += line.quantity
        after_qty = item.quantity

        log = InventoryLog(
            item_id=item.id,
            action="in",
            quantity=line.quantity,
            before_qty=before_qty,
            after_qty=after_qty,
            reference_type="purchase_order",
            reference_id=po.id,
            notes=f"進貨單 {po.order_no} 收貨入庫",
            tenant_id=po.tenant_id,
            created_by=user_id,
        )
        db.add(log)

    db.commit()


def process_sales_ship(db: Session, so: SalesOrder, user_id: int = None):
    """Process inventory decrease when a sales order is shipped.

    For each line in the SO, decrease item.quantity and write an inventory log.
    Allows negative stock (不限制出庫，允許負庫存記錄).
    """
    for line in so.lines:
        item = db.query(Item).filter(Item.id == line.item_id).first()
        if not item:
            continue

        before_qty = item.quantity
        item.quantity -= line.quantity
        after_qty = item.quantity

        log = InventoryLog(
            item_id=item.id,
            action="out",
            quantity=-line.quantity,
            before_qty=before_qty,
            after_qty=after_qty,
            reference_type="sales_order",
            reference_id=so.id,
            notes=f"銷貨單 {so.order_no} 出貨扣庫",
            tenant_id=so.tenant_id,
            created_by=user_id,
        )
        db.add(log)

    db.commit()
