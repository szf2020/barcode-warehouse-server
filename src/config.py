"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings from .env file."""

    # PostgreSQL
    PGHOST: str = os.getenv("PGHOST", "localhost")
    PGPORT: int = int(os.getenv("PGPORT", "5432"))
    PGUSER: str = os.getenv("PGUSER", "user")
    PGPASSWORD: str = os.getenv("PGPASSWORD", "password")
    PGDATABASE: str = os.getenv("PGDATABASE", "warehouse")

    # MQTT
    MQTT_BROKER: str = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_TOPIC_QUERY: str = os.getenv("MQTT_TOPIC_QUERY", "warehouse/query")
    MQTT_TOPIC_CREATE: str = os.getenv("MQTT_TOPIC_CREATE", "warehouse/create")
    MQTT_TOPIC_RESPONSE: str = os.getenv("MQTT_TOPIC_RESPONSE", "warehouse/response")

    @property
    def database_url(self) -> str:
        """SQLAlchemy database URL."""
        return (
            f"postgresql://{self.PGUSER}:{self.PGPASSWORD}"
            f"@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"
        )


settings = Settings()
