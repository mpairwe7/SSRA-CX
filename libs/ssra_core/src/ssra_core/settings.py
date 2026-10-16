"""Centralised settings and structured JSON logging for SSRA Assist."""

from __future__ import annotations

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SSRA_", extra="ignore")

    environment: str = "local"
    service_name: str = "ssra-service"
    log_level: str = "INFO"
    default_timezone: str = "Africa/Juba"
    current_knowledge_snapshot: str = "2026.10.1"
    force_degradation_level: int = 1
    agentgateway_url: str = "http://localhost:8090"
    api_url: str = "http://localhost:8000"
    runtime_url: str = "http://localhost:8001"


def configure_logging(service_name: str = "ssra-service") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service_name)
