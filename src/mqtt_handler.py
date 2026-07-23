"""MQTT handler — subscribes to barcode queries and publishes responses."""

import json
import logging
import threading
from typing import Optional

import paho.mqtt.client as mqtt

from src.config import settings
from src.database import SessionLocal
from src.models import ItemCreate
from src.services import warehouse_service

logger = logging.getLogger(__name__)


class MQTTHandler:
    """Handles MQTT communication with ESP32 barcode scanner devices."""

    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start MQTT client in a background thread."""
        self.client = mqtt.Client(
            client_id="barcode-warehouse-server",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        try:
            self.client.connect(settings.MQTT_BROKER, settings.MQTT_PORT, keepalive=60)
            self._thread = threading.Thread(target=self.client.loop_forever, daemon=True)
            self._thread.start()
            logger.info(
                f"MQTT connected to {settings.MQTT_BROKER}:{settings.MQTT_PORT}"
            )
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")

    def stop(self):
        """Stop MQTT client."""
        if self.client:
            self.client.disconnect()
            logger.info("MQTT disconnected")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Subscribe to topics on successful connection."""
        client.subscribe(settings.MQTT_TOPIC_QUERY)
        client.subscribe(settings.MQTT_TOPIC_CREATE)
        client.subscribe("warehouse/stock/in")
        client.subscribe("warehouse/stock/out")
        client.subscribe("warehouse/stocktake/scan")
        client.subscribe("warehouse/stocktake/start")
        client.subscribe("warehouse/stocktake/end")
        logger.info(
            f"Subscribed to: {settings.MQTT_TOPIC_QUERY}, {settings.MQTT_TOPIC_CREATE}, "
            "warehouse/stock/in, warehouse/stock/out, warehouse/stocktake/*"
        )

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            topic = msg.topic

            if topic == settings.MQTT_TOPIC_QUERY:
                self._handle_query(payload)
            elif topic == settings.MQTT_TOPIC_CREATE:
                self._handle_create(payload)
            elif topic == "warehouse/stock/in":
                self._handle_stock_in(payload)
            elif topic == "warehouse/stock/out":
                self._handle_stock_out(payload)
            elif topic == "warehouse/stocktake/scan":
                self._handle_stocktake_scan(payload)
            elif topic == "warehouse/stocktake/start":
                self._handle_stocktake_start(payload)
            elif topic == "warehouse/stocktake/end":
                self._handle_stocktake_end(payload)
            else:
                logger.warning(f"Unknown topic: {topic}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _handle_query(self, payload: dict):
        """
        Handle barcode query request.

        Expected payload:
            {"barcode": "4710088123456", "device_id": "esp32-001"}
        Response published to:
            warehouse/response/{device_id}
        """
        barcode = payload.get("barcode")
        device_id = payload.get("device_id", "unknown")

        if not barcode:
            self._publish_response(device_id, {
                "status": "error",
                "message": "barcode field is required",
            })
            return

        db = SessionLocal()
        try:
            item = warehouse_service.get_by_barcode(db, barcode)
            if item:
                self._publish_response(device_id, {
                    "status": "found",
                    "data": {
                        "barcode": item.barcode,
                        "name": item.name,
                        "spec": item.spec,
                        "quantity": item.quantity,
                        "location": item.location,
                        "supplier": item.supplier,
                        "date_in": item.date_in.isoformat() if item.date_in else None,
                    },
                })
            else:
                self._publish_response(device_id, {
                    "status": "not_found",
                    "barcode": barcode,
                    "message": "Item not found in database",
                })
        finally:
            db.close()

    def _handle_create(self, payload: dict):
        """
        Handle item creation request.

        Expected payload:
            {
                "device_id": "esp32-001",
                "barcode": "4710088123456",
                "name": "零件A",
                "spec": "10x20mm",
                "quantity": 100,
                "location": "A-01-03",
                "supplier": "供應商X"
            }
        """
        device_id = payload.get("device_id", "unknown")

        try:
            item_data = ItemCreate(
                barcode=payload["barcode"],
                name=payload["name"],
                spec=payload.get("spec"),
                quantity=payload.get("quantity", 0),
                location=payload.get("location"),
                supplier=payload.get("supplier"),
            )
        except (KeyError, ValueError) as e:
            self._publish_response(device_id, {
                "status": "error",
                "message": f"Invalid payload: {e}",
            })
            return

        db = SessionLocal()
        try:
            # Check if barcode already exists
            existing = warehouse_service.get_by_barcode(db, item_data.barcode)
            if existing:
                self._publish_response(device_id, {
                    "status": "error",
                    "message": f"Barcode {item_data.barcode} already exists",
                })
                return

            item = warehouse_service.create_item(db, item_data)
            self._publish_response(device_id, {
                "status": "created",
                "data": {
                    "barcode": item.barcode,
                    "name": item.name,
                },
            })
        finally:
            db.close()

    def _handle_stock_in(self, payload: dict):
        """
        Handle stock-in scan (入庫).

        Payload: {"device_id": "esp32-001", "barcode": "...", "quantity": 10, "purchase_order_id": 5}
        """
        device_id = payload.get("device_id", "unknown")
        barcode = payload.get("barcode")
        quantity = payload.get("quantity", 1)

        if not barcode:
            self._publish_response(device_id, {"status": "error", "message": "barcode required"})
            return

        db = SessionLocal()
        try:
            from src.models.item import Item
            from src.models.inventory import InventoryLog

            item = db.query(Item).filter(Item.barcode == barcode).first()
            if not item:
                self._publish_response(device_id, {"status": "error", "message": f"Item {barcode} not found"})
                return

            before_qty = item.quantity
            item.quantity += quantity
            after_qty = item.quantity

            log = InventoryLog(
                item_id=item.id,
                action="in",
                quantity=quantity,
                before_qty=before_qty,
                after_qty=after_qty,
                reference_type="purchase_order" if payload.get("purchase_order_id") else "manual",
                reference_id=payload.get("purchase_order_id"),
                notes=f"MQTT scan-in by {device_id}",
                tenant_id=item.tenant_id,
            )
            db.add(log)
            db.commit()

            self._publish_response(device_id, {
                "status": "stock_in_ok",
                "data": {"barcode": barcode, "name": item.name, "quantity": after_qty, "added": quantity},
            })
        finally:
            db.close()

    def _handle_stock_out(self, payload: dict):
        """
        Handle stock-out scan (出庫).

        Payload: {"device_id": "esp32-001", "barcode": "...", "quantity": 2, "sales_order_id": 12}
        """
        device_id = payload.get("device_id", "unknown")
        barcode = payload.get("barcode")
        quantity = payload.get("quantity", 1)

        if not barcode:
            self._publish_response(device_id, {"status": "error", "message": "barcode required"})
            return

        db = SessionLocal()
        try:
            from src.models.item import Item
            from src.models.inventory import InventoryLog

            item = db.query(Item).filter(Item.barcode == barcode).first()
            if not item:
                self._publish_response(device_id, {"status": "error", "message": f"Item {barcode} not found"})
                return

            before_qty = item.quantity
            item.quantity -= quantity
            after_qty = item.quantity

            log = InventoryLog(
                item_id=item.id,
                action="out",
                quantity=-quantity,
                before_qty=before_qty,
                after_qty=after_qty,
                reference_type="sales_order" if payload.get("sales_order_id") else "manual",
                reference_id=payload.get("sales_order_id"),
                notes=f"MQTT scan-out by {device_id}",
                tenant_id=item.tenant_id,
            )
            db.add(log)
            db.commit()

            self._publish_response(device_id, {
                "status": "stock_out_ok",
                "data": {"barcode": barcode, "name": item.name, "quantity": after_qty, "removed": quantity},
            })
        finally:
            db.close()

    def _handle_stocktake_start(self, payload: dict):
        """
        Start a stocktake session.

        Payload: {"device_id": "esp32-001", "tenant_id": 1}
        """
        device_id = payload.get("device_id", "unknown")
        tenant_id = payload.get("tenant_id", 1)

        db = SessionLocal()
        try:
            from src.models.inventory import StocktakeSession
            from datetime import date
            from sqlalchemy import func

            date_str = date.today().strftime("%Y%m%d")
            count = db.query(func.count(StocktakeSession.id)).filter(
                StocktakeSession.session_no.like(f"ST-{date_str}-%"),
                StocktakeSession.tenant_id == tenant_id,
            ).scalar() or 0

            session = StocktakeSession(
                session_no=f"ST-{date_str}-{count + 1:03d}",
                status="counting",
                tenant_id=tenant_id,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            self._publish_response(device_id, {
                "status": "stocktake_started",
                "data": {"session_id": session.id, "session_no": session.session_no},
            })
        finally:
            db.close()

    def _handle_stocktake_scan(self, payload: dict):
        """
        Record a stocktake scan.

        Payload: {"device_id": "esp32-001", "session_id": 3, "barcode": "...", "actual_qty": 48}
        """
        device_id = payload.get("device_id", "unknown")
        session_id = payload.get("session_id")
        barcode = payload.get("barcode")
        actual_qty = payload.get("actual_qty")

        if not all([session_id, barcode, actual_qty is not None]):
            self._publish_response(device_id, {"status": "error", "message": "session_id, barcode, actual_qty required"})
            return

        db = SessionLocal()
        try:
            from src.models.item import Item
            from src.models.inventory import StocktakeSession, StocktakeItem

            session = db.query(StocktakeSession).filter(
                StocktakeSession.id == session_id,
                StocktakeSession.status == "counting",
            ).first()
            if not session:
                self._publish_response(device_id, {"status": "error", "message": "Session not found or closed"})
                return

            item = db.query(Item).filter(Item.barcode == barcode).first()
            if not item:
                self._publish_response(device_id, {"status": "error", "message": f"Item {barcode} not found"})
                return

            st_item = StocktakeItem(
                session_id=session_id,
                item_id=item.id,
                system_qty=item.quantity,
                actual_qty=actual_qty,
                difference=actual_qty - item.quantity,
            )
            db.add(st_item)
            db.commit()

            self._publish_response(device_id, {
                "status": "stocktake_scanned",
                "data": {
                    "barcode": barcode,
                    "name": item.name,
                    "system_qty": item.quantity,
                    "actual_qty": actual_qty,
                    "difference": actual_qty - item.quantity,
                },
            })
        finally:
            db.close()

    def _handle_stocktake_end(self, payload: dict):
        """
        End a stocktake session.

        Payload: {"device_id": "esp32-001", "session_id": 3}
        """
        device_id = payload.get("device_id", "unknown")
        session_id = payload.get("session_id")

        if not session_id:
            self._publish_response(device_id, {"status": "error", "message": "session_id required"})
            return

        db = SessionLocal()
        try:
            from src.models.inventory import StocktakeSession
            from datetime import datetime

            session = db.query(StocktakeSession).filter(
                StocktakeSession.id == session_id,
                StocktakeSession.status == "counting",
            ).first()
            if not session:
                self._publish_response(device_id, {"status": "error", "message": "Session not found or already closed"})
                return

            session.status = "closed"
            session.end_time = datetime.now()
            db.commit()

            self._publish_response(device_id, {
                "status": "stocktake_ended",
                "data": {"session_id": session.id, "session_no": session.session_no},
            })
        finally:
            db.close()

    def _publish_response(self, device_id: str, payload: dict):
        """Publish response to device-specific topic."""
        topic = f"{settings.MQTT_TOPIC_RESPONSE}/{device_id}"
        message = json.dumps(payload, ensure_ascii=False)
        self.client.publish(topic, message)
        logger.info(f"Published to {topic}: {message[:100]}")


# Singleton instance
mqtt_handler = MQTTHandler()
