"""Contract-derived reference and production route-matrix assurance tests."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

import httpx
import pytest
from ssra_api import create_api_app

type HttpMethod = Literal["DELETE", "GET", "PATCH", "POST", "PUT"]
type OperationKey = tuple[HttpMethod, str]

_OPENAPI_METHODS: dict[str, HttpMethod] = {
    "delete": "DELETE",
    "get": "GET",
    "patch": "PATCH",
    "post": "POST",
    "put": "PUT",
}


@dataclass(frozen=True)
class RequestData:
    """Safe synthetic inputs for one documented operation."""

    query: Mapping[str, str] = field(default_factory=dict)
    body: Mapping[str, object] | None = None


@dataclass(frozen=True)
class RouteSample:
    """A concrete non-production request derived from an OpenAPI operation."""

    operation_id: str
    method: HttpMethod
    path_template: str
    path: str
    query: Mapping[str, str]
    body: Mapping[str, object] | None

    @property
    def key(self) -> OperationKey:
        return (self.method, self.path_template)


_NO_REQUEST = RequestData()

# Every callable OpenAPI operation needs an explicit entry. Concrete path values
# are generated below, and all bodies are synthetic test fixtures.
ROUTE_CASES: dict[OperationKey, RequestData] = {
    ("GET", "/healthz"): _NO_REQUEST,
    ("GET", "/v1/admin/audit-verify"): _NO_REQUEST,
    ("GET", "/v1/admin/feature-flags"): _NO_REQUEST,
    ("POST", "/v1/admin/feature-flags"): RequestData(
        body={"flag_name": "route-matrix", "enabled": True, "rollout_pct": 100}
    ),
    ("POST", "/v1/admin/jit-elevation"): RequestData(
        body={
            "requester_staff_id": "synthetic-requester",
            "approver_staff_id": "synthetic-approver",
            "passkey_verified": True,
            "device_posture_compliant": True,
            "duration_minutes": 30,
            "reason": "Synthetic route-matrix request",
        }
    ),
    ("GET", "/v1/admin/kill-switches"): _NO_REQUEST,
    ("POST", "/v1/admin/kill-switches"): RequestData(
        body={"degradation_level": 1, "disabled_tools": [], "disabled_channels": []}
    ),
    ("GET", "/v1/admin/public-status"): _NO_REQUEST,
    ("GET", "/v1/analytics/cx-scorecard"): _NO_REQUEST,
    ("GET", "/v1/analytics/drift-monitors"): RequestData(
        query={"intent_kl": "0.04", "abstention_rate": "0.07", "guardrail_rate": "0.01"}
    ),
    ("POST", "/v1/analytics/feedback"): RequestData(
        body={
            "conversation_id": "conv-route-matrix",
            "csat": 5,
            "reason": "ACCURATE",
            "locale": "en",
        }
    ),
    ("GET", "/v1/analytics/insights"): _NO_REQUEST,
    ("GET", "/v1/analytics/summary"): _NO_REQUEST,
    ("GET", "/v1/appointments/slots"): RequestData(query={"office_code": "JUBA_HQ"}),
    ("POST", "/v1/cases"): RequestData(
        body={
            "case_type": "INQUIRY",
            "summary": "Synthetic route-matrix case",
            "priority": "NORMAL",
        }
    ),
    ("POST", "/v1/cases/{case_id}/maker-checker"): RequestData(
        body={
            "maker_staff_id": "synthetic-maker",
            "checker_staff_id": "synthetic-checker",
            "action_type": "ROUTE_MATRIX",
            "rationale": "Synthetic route-matrix approval",
        }
    ),
    ("POST", "/v1/consent"): RequestData(
        body={
            "subject_ref": "sub-route-matrix",
            "channel": "web",
            "purpose": "SYNTHETIC_TEST",
            "revoked": False,
        }
    ),
    ("DELETE", "/v1/consent/preferences/{subject_ref}"): _NO_REQUEST,
    ("PUT", "/v1/consent/preferences/{subject_ref}"): RequestData(
        body={
            "preferred_locale": "en",
            "preferred_channel": "web",
            "low_data_mode": False,
            "voice_first_a11y": False,
        }
    ),
    ("POST", "/v1/conversations"): RequestData(
        body={"channel": "web", "locale": "en", "office_code": "JUBA_HQ"}
    ),
    ("GET", "/v1/conversations/inbox"): RequestData(query={"office_code": "JUBA_HQ"}),
    ("GET", "/v1/conversations/inbox/stream"): RequestData(query={"office_code": "JUBA_HQ"}),
    ("POST", "/v1/conversations/{conversation_id}/copilot-draft"): RequestData(
        body={"taxpayer_question": "Synthetic route-matrix question"}
    ),
    ("POST", "/v1/conversations/{conversation_id}/handback"): RequestData(
        body={
            "officer_id": "synthetic-officer",
            "resolution_summary": "Synthetic route-matrix resolution",
            "approved_next_intent": "guided_filing_and_payment",
            "return_to_ai_step": 1,
        }
    ),
    ("POST", "/v1/conversations/{conversation_id}/qa-score"): RequestData(
        body={
            "accuracy": 1.0,
            "citations_complete": 1.0,
            "neutrality": 1.0,
            "language_quality": 1.0,
        }
    ),
    ("POST", "/v1/conversations/{conversation_id}/takeover"): RequestData(
        body={"staff_id": "synthetic-officer"}
    ),
    ("POST", "/v1/identity-link/document-precheck"): RequestData(
        body={"mime_type": "application/pdf", "size_bytes": 120_000, "sha256_hex": "a" * 64}
    ),
    ("POST", "/v1/identity-link/documents/analyze"): RequestData(
        body={
            "filename": "synthetic.pdf",
            "text_content": "Synthetic route-matrix document",
            "size_bytes": 120_000,
            "kind": "pdf",
        }
    ),
    ("POST", "/v1/identity-link/verify-otp"): RequestData(
        body={
            "tin": "2003005678",
            "otp_code": "123456",
            "step_up": True,
            "sim_swap_recent": False,
        }
    ),
    ("GET", "/v1/knowledge-admin/active-snapshot"): _NO_REQUEST,
    ("POST", "/v1/knowledge-admin/snapshots"): RequestData(
        body={"version": "2099.1.1-route-matrix", "content_digest_input": "Synthetic fixture"}
    ),
    ("POST", "/v1/knowledge-admin/snapshots/rollback"): _NO_REQUEST,
    ("POST", "/v1/knowledge-admin/snapshots/{version}/approve"): RequestData(
        body={"legal_approver": "synthetic-checker"}
    ),
    ("POST", "/v1/knowledge-admin/snapshots/{version}/publish"): RequestData(
        body={"eval_regression_passed": True}
    ),
    ("POST", "/v1/knowledge-admin/snapshots/{version}/submit-review"): _NO_REQUEST,
}


def _contract_operations() -> dict[OperationKey, Mapping[str, object]]:
    """Return documented Core API endpoints while excluding framework pages."""
    raw_paths = create_api_app().openapi().get("paths")
    assert isinstance(raw_paths, Mapping)

    operations: dict[OperationKey, Mapping[str, object]] = {}
    for path, path_item in raw_paths.items():
        assert isinstance(path, str)
        if path != "/healthz" and not path.startswith("/v1/"):
            continue
        assert isinstance(path_item, Mapping)
        for method, operation in path_item.items():
            http_method = _OPENAPI_METHODS.get(method) if isinstance(method, str) else None
            if http_method is None:
                continue
            assert isinstance(operation, Mapping)
            operations[(http_method, path)] = operation
    return operations


def _route_matrix() -> tuple[RouteSample, ...]:
    """Build the concrete request list only after contract coverage is complete."""
    operations = _contract_operations()
    assert set(ROUTE_CASES) == set(operations), "route-matrix coverage drift"
    samples: list[RouteSample] = []
    for (method, template), data in sorted(ROUTE_CASES.items()):
        operation_id = operations[(method, template)].get("operationId")
        assert isinstance(operation_id, str) and operation_id
        samples.append(
            RouteSample(
                operation_id=operation_id,
                method=method,
                path_template=template,
                path=re.sub(r"\{[^}]+\}", "route-matrix", template),
                query=data.query,
                body=data.body,
            )
        )
    return tuple(samples)


def _reference_status(operation: Mapping[str, object]) -> int:
    """Infer the intended reference result from documented error responses."""
    raw_responses = operation.get("responses")
    assert isinstance(raw_responses, Mapping)
    statuses = {
        int(status) for status in raw_responses if isinstance(status, str) and status.isdigit()
    }
    if 403 in statuses:
        return 403
    if 503 in statuses:
        return 503
    assert 200 in statuses
    return 200


async def _request_matrix() -> list[tuple[RouteSample, httpx.Response]]:
    """Exercise the ASGI app directly so early denials cannot hang the test client."""
    transport = httpx.ASGITransport(app=create_api_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        responses: list[tuple[RouteSample, httpx.Response]] = []
        for sample in _route_matrix():
            response = await client.request(
                sample.method,
                sample.path,
                params=sample.query or None,
                json=sample.body,
            )
            responses.append((sample, response))
    return responses


def _assert_problem_response(
    response: httpx.Response, *, expected_status: int, instance: str
) -> None:
    """Check the non-cacheable RFC 9457 envelope shared by all denials."""
    assert response.status_code == expected_status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["traceparent"]
    assert "etag" not in response.headers
    body = response.json()
    assert body["status"] == expected_status
    assert body["instance"] == instance
    assert body["code"] == ("NOT_AUTHORIZED" if expected_status == 403 else "UPSTREAM_UNAVAILABLE")


def test_route_matrix_has_one_safe_case_for_every_callable_openapi_operation() -> None:
    """Require a conscious safe request whenever the public Core API grows."""
    operations = _contract_operations()
    samples = _route_matrix()

    assert len(samples) == len({sample.key for sample in samples})
    assert {sample.key for sample in samples} == set(operations)
    for sample in samples:
        assert operations[sample.key].get("operationId") == sample.operation_id
        assert "{" not in sample.path
        assert _reference_status(operations[sample.key]) in {200, 403, 503}


@pytest.mark.parametrize("runtime_mode", [None, "", "production", "unknown"])
def test_every_contract_route_fails_closed_outside_reference_mode(
    monkeypatch: pytest.MonkeyPatch, runtime_mode: str | None
) -> None:
    """Production and invalid modes cannot expose reference handlers or state."""
    if runtime_mode is None:
        monkeypatch.delenv("SSRA_RUNTIME_MODE", raising=False)
    else:
        monkeypatch.setenv("SSRA_RUNTIME_MODE", runtime_mode)

    for sample, response in asyncio.run(_request_matrix()):
        _assert_problem_response(response, expected_status=503, instance=sample.path)


def test_reference_mode_matches_documented_contract_route_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reference mode remains explicit while staff and unapproved providers stay unavailable."""
    monkeypatch.setenv("SSRA_RUNTIME_MODE", "reference")
    operations = _contract_operations()

    for sample, response in asyncio.run(_request_matrix()):
        expected_status = _reference_status(operations[sample.key])
        assert response.headers["x-ssra-runtime-mode"] == "reference"
        if expected_status == 200:
            assert response.status_code == 200
            continue
        _assert_problem_response(response, expected_status=expected_status, instance=sample.path)


def test_reference_mode_normalizes_case_but_never_accepts_blank_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Document intentional case normalization and protect the empty-value fail-safe."""
    monkeypatch.setenv("SSRA_RUNTIME_MODE", "REFERENCE")
    reference_health = next(
        response
        for sample, response in asyncio.run(_request_matrix())
        if sample.key == ("GET", "/healthz")
    )
    assert reference_health.status_code == 200

    monkeypatch.setenv("SSRA_RUNTIME_MODE", "")
    blank_mode_health = next(
        response
        for sample, response in asyncio.run(_request_matrix())
        if sample.key == ("GET", "/healthz")
    )
    _assert_problem_response(blank_mode_health, expected_status=503, instance="/healthz")
