# src/agent/settings.py
"""Loads settings from environment variables."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    http_path: str
    client_id: str
    client_secret: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        def get_required(name: str) -> str:
            value = os.getenv(name)

            if not value:
                raise ValueError(
                    f"Missing required environment variable: {name}"
                )

            return value

        return cls(
            host=get_required("DATABRICKS_HOST"),
            http_path=get_required("DATABRICKS_HTTP_PATH"),
            client_id=get_required("DATABRICKS_CLIENT_ID"),
            client_secret=get_required("DATABRICKS_CLIENT_SECRET"),
        )
