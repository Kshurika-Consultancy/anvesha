"""Explicit environment configuration shared by API and worker (ANV-004)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from anvesha.llm import LLMConfig
from anvesha.retention import DEFAULT_SECONDS, seconds_from_env, validate_seconds

SUPPORTED_SOURCES = frozenset({"local", "wikidata", "wikipedia"})


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(".anvesha/anvesha.db")
    api_keys: tuple[str, ...] = ()
    enabled_sources: tuple[str, ...] = ("local",)
    worker_poll_seconds: float = 1.0
    llm: LLMConfig = field(default_factory=LLMConfig)
    retention_seconds: int = DEFAULT_SECONDS
    wikipedia_user_agent: str = ""

    def __post_init__(self):
        validate_seconds(self.retention_seconds)
        if not self.enabled_sources or set(self.enabled_sources) - SUPPORTED_SOURCES:
            raise ValueError("Enabled sources must be local, wikidata and/or wikipedia")
        if not isinstance(self.wikipedia_user_agent, str):
            raise ValueError(
                "Wikipedia User-Agent must be identifying text with contact information"
            )
        if self.wikipedia_user_agent or "wikipedia" in self.enabled_sources:
            from anvesha.providers import ProviderError, _user_agent

            try:
                _user_agent(value=self.wikipedia_user_agent)
            except ProviderError:
                raise ValueError(
                    "Wikipedia requires an Anvesha User-Agent with real contact"
                ) from None
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
            llm=LLMConfig.from_env(),
            retention_seconds=seconds_from_env(),
            wikipedia_user_agent=os.getenv("ANVESHA_WIKIPEDIA_USER_AGENT", ""),
        )
