"""Typed MCP errors (Section 8.3) and RFC 9457 Problem Details (Section 10.4)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class McpErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"


class ProblemDetails(BaseModel):
    """RFC 9457 Problem Details for HTTP APIs."""

    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: McpErrorCode | str | None = None
    trace_id: str | None = None


class SSRAError(Exception):
    """Domain/service error mapped deterministically to McpErrorCode and HTTP status."""

    def __init__(
        self,
        code: McpErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_problem_details(
        self, *, instance: str | None = None, trace_id: str | None = None
    ) -> ProblemDetails:
        return ProblemDetails(
            type=f"https://ssra.gov.ss/problems/{self.code.lower()}",
            title=self.code.value.replace("_", " ").title(),
            status=self.status_code,
            detail=self.message,
            instance=instance,
            code=self.code,
            trace_id=trace_id,
        )
