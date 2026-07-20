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
        logger.info(
            f"Subscribed to: {settings.MQTT_TOPIC_QUERY}, {settings.MQTT_TOPIC_CREATE}"
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

    def _publish_response(self, device_id: str, payload: dict):
        """Publish response to device-specific topic."""
        topic = f"{settings.MQTT_TOPIC_RESPONSE}/{device_id}"
        message = json.dumps(payload, ensure_ascii=False)
        self.client.publish(topic, message)
        logger.info(f"Published to {topic}: {message[:100]}")


# Singleton instance
mqtt_handler = MQTTHandler()
