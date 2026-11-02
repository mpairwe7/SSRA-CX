"""PostgreSQL 18 Row-Level Security (RLS) Session Context & Repository Helpers (`services/api/src/ssra_api/repositories.py` — Section 17)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ssra_core import McpErrorCode, SSRAError

_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_SAFE_STAFF_ID_RE = re.compile(r"^[A-Za-z0-9_:-]{1,64}$")
_ALLOWED_STAFF_ROLES = frozenset(
    {"agent", "supervisor", "qa", "legal_approver", "secops", "admin", "auditor"}
)


@dataclass(frozen=True)
class PostgresRlsSessionContext:
    staff_id: str
    office_code: str
    staff_role: str

    def to_set_local_sql(self) -> tuple[str, ...]:
        """Generate parameterized/validated `SET LOCAL` statements for PostgreSQL 18 RLS scoping, timeouts, and read-only Auditor SoD."""
        if not _SAFE_STAFF_ID_RE.match(self.staff_id):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Invalid staff_id format for RLS context",
                status_code=400,
            )
        if not _SAFE_TOKEN_RE.match(self.office_code):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Invalid office_code format for RLS context",
                status_code=400,
            )
        if self.staff_role not in _ALLOWED_STAFF_ROLES:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Unknown staff_role '{self.staff_role}' for RLS context",
                status_code=403,
            )
        stmts = [
            f"SET LOCAL ssra.staff_office_code = '{self.office_code}';",
            f"SET LOCAL ssra.staff_role = '{self.staff_role}';",
            f"SET LOCAL ssra.staff_id = '{self.staff_id}';",
            "SET LOCAL statement_timeout = '5000ms';",
            "SET LOCAL lock_timeout = '2000ms';",
        ]
        if self.staff_role == "auditor":
            stmts.append("SET LOCAL transaction_read_only = on;")
        return tuple(stmts)
