"""Structured JSON logging, W3C trace correlation, and PII sanitization (`libs/ssra_core/src/ssra_core/logging_config.py`).

Transferred and adapted from `FinalYearProject/App/backend/app/logging_config.py` and `tracing.py`
for SSRA Assist (October 2026 OpenTelemetry Log Data Model & OWASP ASVS 5.0 V16).
"""

from __future__ import annotations

import contextvars
import datetime
import json
import logging
import os
import re
import traceback
from typing import Any

from ssra_core.telemetry import ensure_w3c_traceparent

REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
ACTIVE_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
ACTIVE_SPAN_ID: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="")

_HANDLER_MARK = "_ssra_log_handler"
_SEVERITY_NUMBER: dict[int, int] = {
    logging.DEBUG: 5,
    logging.INFO: 9,
    logging.WARNING: 13,
    logging.ERROR: 17,
    logging.CRITICAL: 21,
}
_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("x", logging.INFO, "x", 0, "", None, None)).keys()
) | {
    "message",
    "asctime",
    "request_id",
    "trace_id",
    "span_id",
    "otelSpanID",
    "otelTraceID",
    "otelTraceSampled",
    "otelServiceName",
}
_NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "hpack", "multipart")

_LOG_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?211[\s-]?(?:\(0\)[\s-]?)?0?[19]\d{2}[\s-]?\d{3}[\s-]?\d{3}|"
    r"0[179]\d{2}[\s-]?\d{3}[\s-]?\d{3}|07\d{8})(?!\w)"
)
_LOG_TIN_RE = re.compile(r"\b(?:\d{9,12}|\d{3}[\s-]\d{3}[\s-]?\d{4})\b")
_LOG_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]{1,64})@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_LOG_OTP_RE = re.compile(r"\b(otp|passcode|verification\s+code)\s*[:=]?\s*\d{4,8}\b", re.IGNORECASE)
_ALLOWED_OFFICIAL_EMAIL_DOMAINS = frozenset({"nra.gov.ss", "ssra.gov.ss", "etax.nra.gov.ss"})


def redact_log_pii_text(text: str) -> str:
    """Scrub taxpayer TINs, phone numbers, emails (preserving official SSRA/NRA domains), and OTPs from log text."""
    if not text:
        return text

    def _email_repl(match: re.Match[str]) -> str:
        domain = match.group(2).lower()
        if domain in _ALLOWED_OFFICIAL_EMAIL_DOMAINS:
            return match.group(0)
        return "[REDACTED_EMAIL]"

    scrubbed = _LOG_EMAIL_RE.sub(_email_repl, text)
    scrubbed = _LOG_OTP_RE.sub(r"\1=[REDACTED_OTP]", scrubbed)
    scrubbed = _LOG_PHONE_RE.sub("[REDACTED_PHONE]", scrubbed)
    return _LOG_TIN_RE.sub("[REDACTED_TIN]", scrubbed)


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_log_pii_text(value)
    if isinstance(value, dict):
        return {k: _scrub_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub_value(item) for item in value)
    return value


def extract_w3c_trace_context(traceparent: str | None = None) -> tuple[str, str, str]:
    """Validate or mint a W3C `traceparent`, bind `trace_id` and `span_id` to contextvars, and return `(traceparent, trace_id, span_id)`."""
    resolved = ensure_w3c_traceparent(traceparent)
    parts = resolved.split("-")
    trace_id = parts[1] if len(parts) >= 3 else ""
    span_id = parts[2] if len(parts) >= 3 else ""
    ACTIVE_TRACE_ID.set(trace_id)
    ACTIVE_SPAN_ID.set(span_id)
    return resolved, trace_id, span_id


def get_current_trace_id() -> str:
    """Return the active W3C 32-hex `trace_id` for the current execution context."""
    return ACTIVE_TRACE_ID.get()


def get_current_span_id() -> str:
    """Return the active W3C 16-hex `span_id` for the current execution context."""
    return ACTIVE_SPAN_ID.get()


def get_current_request_id() -> str:
    """Return the active `X-Request-ID` for the current execution context."""
    return REQUEST_ID.get()


class RequestContextFilter(logging.Filter):
    """Stamp `request_id`, `trace_id`, and `span_id` from contextvars onto every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            req_id = REQUEST_ID.get()
            if req_id:
                record.request_id = req_id
        if not getattr(record, "trace_id", None):
            tr_id = ACTIVE_TRACE_ID.get()
            if tr_id:
                record.trace_id = tr_id
        if not getattr(record, "span_id", None):
            sp_id = ACTIVE_SPAN_ID.get()
            if sp_id:
                record.span_id = sp_id
        return True


class PIISanitizingFilter(logging.Filter):
    """Redact PII from the log message, its arguments, `extra=` fields, and exception tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_log_pii_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _scrub_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_scrub_value(arg) for arg in record.args)
        for key, value in list(vars(record).items()):
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                setattr(record, key, _scrub_value(value))
        if record.exc_info and not record.exc_text:
            record.exc_text = redact_log_pii_text(
                "".join(traceback.format_exception(*record.exc_info)).strip()
            )
        return True


class StructuredJsonFormatter(logging.Formatter):
    """Single-line JSON formatter adhering to the OpenTelemetry Log Data Model."""

    def __init__(self, service_name: str = "ssra-assist-api") -> None:
        super().__init__()
        self.service_name = service_name
        self.service_version = os.getenv("APP_VERSION", "2026.10.1")
        self.environment = os.getenv("SSRA_RUNTIME_MODE", "production")

    def format(self, record: logging.LogRecord) -> str:
        try:
            message = redact_log_pii_text(record.getMessage())
        except Exception:
            message = redact_log_pii_text(str(record.msg))

        log_data: dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.UTC
            ).isoformat(),
            "level": record.levelname,
            "severity_text": record.levelname,
            "severity_number": _SEVERITY_NUMBER.get(record.levelno, 9),
            "logger": record.name,
            "message": message,
            "service": self.service_name,
            "service.version": self.service_version,
            "deployment.environment": self.environment,
        }

        trace_id = getattr(record, "trace_id", None) or get_current_trace_id()
        if trace_id:
            log_data["trace_id"] = trace_id
            log_data["span_id"] = getattr(record, "span_id", None) or get_current_span_id()

        request_id = getattr(record, "request_id", None) or get_current_request_id()
        if request_id:
            log_data["request_id"] = request_id

        attributes = {
            key: value
            for key, value in vars(record).items()
            if key not in _STANDARD_ATTRS and not key.startswith("_")
        }
        if attributes:
            log_data["attributes"] = attributes

        if record.exc_info or record.exc_text:
            raw_exc = (
                record.exc_text
                if record.exc_text
                else "".join(traceback.format_exception(*record.exc_info)).strip()
                if record.exc_info
                else ""
            )
            log_data["exception"] = redact_log_pii_text(raw_exc)

        return json.dumps(log_data, default=str)


def _use_json() -> bool:
    log_format = os.getenv("LOG_FORMAT", "").lower()
    runtime_mode = os.getenv("SSRA_RUNTIME_MODE", "production").lower()
    return log_format == "json" or (log_format != "text" and runtime_mode == "production")


def configure_structured_logging(service_name: str | None = None) -> logging.Handler:
    """Build the stdout handler with `RequestContextFilter`, `PIISanitizingFilter`, and JSON/text formatter."""
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    handler.addFilter(PIISanitizingFilter())
    resolved_service = service_name or os.getenv("OTEL_SERVICE_NAME", "ssra-assist-api")
    if _use_json():
        handler.setFormatter(StructuredJsonFormatter(service_name=resolved_service))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.setLevel(log_level)
    setattr(handler, _HANDLER_MARK, True)
    return handler


def install_logging(service_name: str | None = None) -> logging.Handler:
    """Route every logger through one structured, PII-sanitized handler; idempotent per process."""
    root = logging.getLogger()
    for existing in root.handlers:
        if getattr(existing, _HANDLER_MARK, False):
            return existing
    handler = configure_structured_logging(service_name=service_name)
    root.addHandler(handler)
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)
    for app_pkg in ("ssra", "ssra_api", "ssra_runtime", "ssra_voice", "ssra_security"):
        pkg_logger = logging.getLogger(app_pkg)
        pkg_logger.setLevel(level)
        pkg_logger.propagate = True
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    return handler
