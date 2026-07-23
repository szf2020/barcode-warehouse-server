"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings from .env file."""

    # Database type: "sqlite" or "postgresql"
    DB_TYPE: str = os.getenv("DB_TYPE", "sqlite").lower()

    # SQLite
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./warehouse.db")

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

    # Session
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-a-random-string")

    @property
    def database_url(self) -> str:
        """SQLAlchemy database URL based on DB_TYPE."""
        if self.DB_TYPE == "postgresql":
            return (
                f"postgresql://{self.PGUSER}:{self.PGPASSWORD}"
                f"@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"
            )
        # Default: SQLite
        return f"sqlite:///{self.SQLITE_PATH}"

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        return self.DB_TYPE != "postgresql"


settings = Settings()
