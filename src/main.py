"""Barcode Warehouse Server — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from src.config import settings
from src.database import get_db, init_db
from src.models import ItemCreate, ItemUpdate, ItemResponse
from src.services import warehouse_service
from src.mqtt_handler import mqtt_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("Starting MQTT handler...")
    mqtt_handler.start()
    logger.info("Barcode Warehouse Server is ready.")
    yield
    # Shutdown
    mqtt_handler.stop()
    logger.info("Server shutdown complete.")


app = FastAPI(
    title="Barcode Warehouse Server",
    description="倉管條碼系統後端 — FastAPI + PostgreSQL + MQTT",
    version="0.1.0",
    lifespan=lifespan,
)

# ─── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# ─── Static Files & Templates ───────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ─── Web Routes (Frontend) ──────────────────────────────────────────────────
from src.routes.web import router as web_router  # noqa: E402
from src.routes.partners import router as partners_router  # noqa: E402
from src.routes.purchases import router as purchases_router  # noqa: E402
from src.routes.quotations import router as quotations_router  # noqa: E402
from src.routes.sales import router as sales_router  # noqa: E402
from src.routes.accounting import router as accounting_router  # noqa: E402
from src.routes.repairs import router as repairs_router  # noqa: E402
from src.routes.printing import router as printing_router  # noqa: E402
app.include_router(web_router)
app.include_router(partners_router)
app.include_router(purchases_router)
app.include_router(quotations_router)
app.include_router(sales_router)
app.include_router(accounting_router)
app.include_router(repairs_router)
app.include_router(printing_router)


# ─── REST API Endpoints ─────────────────────────────────────────────────────


@app.get("/")
def root():
    """Redirect to web UI."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/web/login", status_code=302)


@app.get("/items", response_model=List[ItemResponse])
def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List all warehouse items with pagination."""
    return warehouse_service.list_items(db, skip=skip, limit=limit)


@app.get("/items/{barcode}", response_model=ItemResponse)
def get_item(barcode: str, db: Session = Depends(get_db)):
    """Get a single item by barcode."""
    item = warehouse_service.get_by_barcode(db, barcode)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item with barcode '{barcode}' not found")
    return item


@app.post("/items", response_model=ItemResponse, status_code=201)
def create_item(item_data: ItemCreate, db: Session = Depends(get_db)):
    """Create a new warehouse item."""
    existing = warehouse_service.get_by_barcode(db, item_data.barcode)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Item with barcode '{item_data.barcode}' already exists",
        )
    return warehouse_service.create_item(db, item_data)


@app.put("/items/{barcode}", response_model=ItemResponse)
def update_item(barcode: str, item_data: ItemUpdate, db: Session = Depends(get_db)):
    """Update an existing item by barcode."""
    item = warehouse_service.update_item(db, barcode, item_data)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item with barcode '{barcode}' not found")
    return item


@app.delete("/items/{barcode}")
def delete_item(barcode: str, db: Session = Depends(get_db)):
    """Delete an item by barcode."""
    success = warehouse_service.delete_item(db, barcode)
    if not success:
        raise HTTPException(status_code=404, detail=f"Item with barcode '{barcode}' not found")
    return {"status": "deleted", "barcode": barcode}
