"""Warehouse service — CRUD business logic for items."""

from typing import Optional

from sqlalchemy.orm import Session

from src.models import Item, ItemCreate, ItemUpdate


def get_by_barcode(db: Session, barcode: str) -> Optional[Item]:
    """Look up an item by barcode."""
    return db.query(Item).filter(Item.barcode == barcode).first()


def list_items(db: Session, skip: int = 0, limit: int = 100) -> list[Item]:
    """List all items with pagination."""
    return db.query(Item).offset(skip).limit(limit).all()


def create_item(db: Session, item_data: ItemCreate) -> Item:
    """Create a new item in the database."""
    db_item = Item(
        barcode=item_data.barcode,
        name=item_data.name,
        spec=item_data.spec,
        quantity=item_data.quantity,
        location=item_data.location,
        supplier=item_data.supplier,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_item(db: Session, barcode: str, item_data: ItemUpdate) -> Optional[Item]:
    """Update an existing item by barcode."""
    db_item = get_by_barcode(db, barcode)
    if not db_item:
        return None

    update_data = item_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_item(db: Session, barcode: str) -> bool:
    """Delete an item by barcode. Returns True if deleted."""
    db_item = get_by_barcode(db, barcode)
    if not db_item:
        return False

    db.delete(db_item)
    db.commit()
    return True
