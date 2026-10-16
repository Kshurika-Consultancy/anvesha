"""Explicit environment configuration shared by API and worker (ANV-004)."""

import os
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_SOURCES = frozenset({"local", "wikidata"})


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(".anvesha/anvesha.db")
    api_keys: tuple[str, ...] = ()
    enabled_sources: tuple[str, ...] = ("local",)
    worker_poll_seconds: float = 1.0

    def __post_init__(self):
        if not self.enabled_sources or set(self.enabled_sources) - SUPPORTED_SOURCES:
            raise ValueError("Enabled sources must be local and/or wikidata")
        if not 0.1 <= self.worker_poll_seconds <= 60:
            raise ValueError("Worker poll interval must be between 0.1 and 60 seconds")
        if any(
            len(key) < 24 or len(key) > 256 or not key.isascii() or any(c.isspace() for c in key)
            for key in self.api_keys
        ):
            raise ValueError("API keys must contain 24 to 256 ASCII characters")

    @classmethod
    def from_env(cls):
        def parts(name, default=""):
            values = (x.strip() for x in os.getenv(name, default).split(","))
            return tuple(dict.fromkeys(value for value in values if value))

        return cls(
            database_path=Path(os.getenv("ANVESHA_DB_PATH", ".anvesha/anvesha.db")),
            api_keys=parts("ANVESHA_API_KEYS"),
            enabled_sources=parts("ANVESHA_ENABLED_SOURCES", "local"),
            worker_poll_seconds=float(os.getenv("ANVESHA_WORKER_POLL_SECONDS", "1")),
        )
