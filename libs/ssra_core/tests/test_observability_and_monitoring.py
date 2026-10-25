"""Unit and contract tests for SSRA Assist logging, monitoring, and observability (`libs/ssra_core/tests/test_observability_and_monitoring.py`).

Covers:
1. Structured JSON logging, W3C trace context correlation, and PII scrubbing (`logging_config.py`).
2. Prometheus metrics facade, cumulative histograms, label cardinality bounds, chat turn & language recorders, OWASP security events, client RUM telemetry, and turn digest audit records (`observability.py`).
3. API `/metrics` bearer token authentication (`200` vs `401` + `authn_login_fail` event) and `/v1/telemetry/{vitals,errors}` ingestion (`204`, `422`, `413`).
4. Monitoring configuration parity across `prometheus.yml`, `recording-rules.yml`, `alerting-rules.yml`, `alertmanager.yml`, `loki.yaml`, `blackbox.yml`, `otel-collector-config.yaml`, `slo/ssra-assist.openslo.yaml`, and `dashboards/ssra-cx-overview.json`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml
from ssra_api import create_api_app
from ssra_core import (
    ACTIVE_SPAN_ID,
    ACTIVE_TRACE_ID,
    REQUEST_ID,
    ClientError,
    MetricsStore,
    PIISanitizingFilter,
    RequestContextFilter,
    StructuredJsonFormatter,
    WebVital,
    WebVitalsBatch,
    bucket_quantile,
    build_turn_audit_record,
    configure_structured_logging,
    default_buckets,
    exported_name,
    extract_w3c_trace_context,
    get_current_request_id,
    get_current_span_id,
    get_current_trace_id,
    install_logging,
    metrics,
    normalise_route,
    record_chat_turn,
    record_client_error,
    record_http_security_event,
    record_language_decision,
    record_mapped,
    record_mcp_security_event,
    record_qdrant_lifecycle_observation,
    record_security_event,
    record_web_vitals,
    redact_log_pii_text,
    route_label_from_scope,
    turn_outcome,
)
from ssra_testing import AsgiTestClient

ROOT = Path(__file__).resolve().parents[3]
OBS_DIR = ROOT / "infra" / "observability"
REPO_URL = "https://github.com/mpairwe7/SSRA-CX/blob/main/"

_SSRA_SERIES_RE = re.compile(r"\bssra_[a-z0-9_]+")
_SSRA_RECORDING_RE = re.compile(r"\bssra:[a-zA-Z0-9_:]+")


def _format_log(record: logging.LogRecord) -> dict[str, object]:
    for flt in (RequestContextFilter(), PIISanitizingFilter()):
        flt.filter(record)
    return json.loads(StructuredJsonFormatter("ssra-assist-api").format(record))


def _make_record(
    msg: str, *args: object, exc_info: object = None, **extra: object
) -> logging.LogRecord:
    rec = logging.LogRecord("ssra.test", logging.WARNING, __file__, 1, msg, args, exc_info)  # type: ignore[arg-type]
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_structured_logging_trace_correlation_and_pii_scrubbing() -> None:
    tp, tr_id, sp_id = extract_w3c_trace_context(
        "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    )
    assert tp == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert get_current_trace_id() == tr_id
    assert get_current_span_id() == sp_id

    tok = REQUEST_ID.set("req-juba-001")
    try:
        assert get_current_request_id() == "req-juba-001"
        line = _format_log(
            _make_record(
                "lookup for %s",
                "taxpayer@example.com",
                event="pii_redacted",
                authorization="Bearer super-secret-jwt-token",
                contacts=["+211 912 345 678", "support@nra.gov.ss"],
                nested={
                    "tin": "100-200-1234",
                    "otp": "482910",
                    "api_key": "sk-secret-key",
                    "pair": ("0912345678", 42),
                },
                custom_set={"secret_set@example.com"},
            )
        )
    finally:
        REQUEST_ID.reset(tok)

    assert line["request_id"] == "req-juba-001"
    assert line["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert line["span_id"] == "00f067aa0ba902b7"
    assert line["severity_number"] == 13
    assert line["severity_text"] == "WARNING"
    serialized = json.dumps(line)
    assert "taxpayer@example.com" not in serialized
    assert "super-secret-jwt-token" not in serialized
    assert "sk-secret-key" not in serialized
    assert "secret_set@example.com" not in serialized
    assert "912 345 678" not in serialized
    assert "100-200-1234" not in serialized
    assert "482910" not in serialized
    assert "0912345678" not in serialized
    assert "support@nra.gov.ss" in serialized

    # Dict record.args and traceback scrubbing
    rec_dict = logging.LogRecord(
        "ssra.test",
        logging.ERROR,
        __file__,
        1,
        "failed for %(user)s",
        ({"user": "john@gmail.com"},),
        None,
    )
    dict_line = _format_log(rec_dict)
    assert "john@gmail.com" not in json.dumps(dict_line)

    try:
        raise ValueError("lookup failed for email secret_user@yahoo.com and TIN 1234567890")
    except ValueError:
        exc_line = _format_log(_make_record("boom", exc_info=sys.exc_info()))
    assert "ValueError" in str(exc_line.get("exception", ""))
    assert "secret_user@yahoo.com" not in str(exc_line.get("exception", ""))
    assert "1234567890" not in str(exc_line.get("exception", ""))

    assert redact_log_pii_text("") == ""
    with mock.patch.dict(os.environ, {"LOG_FORMAT": "text", "SSRA_RUNTIME_MODE": "reference"}):
        txt_handler = configure_structured_logging("ssra-test")
        assert not isinstance(txt_handler.formatter, StructuredJsonFormatter)
    with mock.patch.dict(os.environ, {"LOG_FORMAT": "json"}):
        json_handler = configure_structured_logging("ssra-test")
        assert isinstance(json_handler.formatter, StructuredJsonFormatter)
    first = install_logging("ssra-test")
    second = install_logging("ssra-test")
    assert first is second
    ACTIVE_TRACE_ID.set("")
    ACTIVE_SPAN_ID.set("")


def test_metrics_store_cumulative_histograms_and_bounded_labels() -> None:
    store = MetricsStore(max_series_per_metric=12)
    store.inc(
        "http_requests_total", labels={"method": "GET", "path": "/healthz\\", "status": "200"}
    )
    text = store.to_prometheus()
    assert 'ssra_http_requests_total{method="GET",path="/healthz\\\\",status="200"} 1.0' in text
    assert "\nhttp_requests_total{" not in text
    assert text.count("# TYPE ssra_http_requests_total counter") == 1

    assert exported_name("chat_turns_total") == "ssra_chat_turns_total"
    assert exported_name("ssra_eval_metric") == "ssra_eval_metric"
    with pytest.raises(ValueError):
        exported_name("bad metric name")
    store.inc("bad_label_metric", labels={"__reserved": "x"})
    assert "ssra_bad_label_metric" not in store.to_prometheus()

    # Cumulative histogram buckets never decrease when slower samples arrive
    for _ in range(50):
        store.observe("chat_response_time_ms", 100.0, labels={"channel": "web", "mode": "hybrid"})
    for _ in range(30):
        store.observe("chat_response_time_ms", 4000.0, labels={"channel": "web", "mode": "hybrid"})
    prom_after = store.to_prometheus()
    assert (
        'ssra_chat_response_time_ms_bucket{channel="web",mode="hybrid",le="3000.0"} 50.0'
        in prom_after
    )
    assert (
        'ssra_chat_response_time_ms_bucket{channel="web",mode="hybrid",le="+Inf"} 80.0'
        in prom_after
    )
    assert 'ssra_chat_response_time_ms_count{channel="web",mode="hybrid"} 80.0' in prom_after

    assert default_buckets("x_ms")[0] == 5.0
    assert 3000.0 in default_buckets("x_ms")
    assert default_buckets("x_seconds")[0] == 0.005
    assert default_buckets("payload_bytes")[0] == 1024.0
    assert default_buckets("faithfulness_score")[-1] == 1.0
    assert default_buckets("items_count")[0] == 1.0

    # Series cardinality cap folds overflow into __other__
    for i in range(25):
        store.inc("probe_total", labels={"path": f"/scan/{i}"})
    assert 'path="__other__"' in store.to_prometheus()

    # Unknown labels dropped and type conflicts ignored safely
    store.inc("labelled_total", labels={"a": "1"})
    store.inc("labelled_total", labels={"a": "2", "unexpected": "x"})
    store.observe("labelled_total", 1.0, labels={"a": "1"})
    store.set_gauge("active_workers", 2.0)
    store.add_gauge("inflight_requests", 3.0)
    store.add_gauge("inflight_requests", -1.0)
    snap = store.snapshot()
    assert snap["counters"]['labelled_total{a="2"}'] == 1
    assert snap["gauges"]["active_workers"] == 2
    assert snap["gauges"]["inflight_requests"] == 2
    hist_snap = snap["histograms"]['chat_response_time_ms{channel="web",mode="hybrid"}']
    assert hist_snap["count"] == 80
    assert hist_snap["p50"] <= hist_snap["p95"] <= hist_snap["p99"]

    assert (
        bucket_quantile(0.5, [(100.0, 50.0), (200.0, 100.0), (float("inf"), 100.0)], 100.0) == 100.0
    )
    assert (
        bucket_quantile(0.75, [(100.0, 50.0), (200.0, 100.0), (float("inf"), 100.0)], 100.0)
        == 150.0
    )
    assert bucket_quantile(0.99, [(1.0, 1.0), (float("inf"), 10.0)], 10.0) == 1.0
    assert bucket_quantile(0.5, [], 0.0) == 0.0


def test_turn_recorders_security_events_client_telemetry_and_turn_audit() -> None:
    assert turn_outcome({"retrieval_mode": "hybrid"}) == "answered"
    assert turn_outcome({"retrieval_mode": "abstained"}) == "abstained"
    assert turn_outcome({"retrieval_mode": "out_of_jurisdiction"}) == "out_of_scope"
    assert turn_outcome({"retrieval_mode": "hybrid", "escalation_required": True}) == "escalated"
    assert turn_outcome({"retrieval_mode": "blocked", "escalation_required": True}) == "blocked"

    for ch in ("web", "sse", "voice", "call"):
        record_chat_turn(
            {
                "retrieval_mode": "hybrid",
                "faithfulness_score": 0.92,
                "locale": "pga",
                "locale_source": "detected",
            },
            elapsed_ms=420.0,
            channel=ch,
        )
    record_chat_turn(
        {
            "retrieval_mode": "abstained",
            "escalation_required": True,
            "locale": "unknown_loc",
            "locale_source": "unknown_src",
        },
        elapsed_ms=15.0,
        channel="web",
    )
    record_language_decision({}, channel="web")

    table = {
        "_c": ("counter", "ws_frames_total", None),
        "_g": ("gauge", "ws_active", None),
        "_h": ("histogram", "ws_latency_ms", (10.0, 100.0)),
    }
    record_mapped(table, "_c")
    record_mapped(table, "_g", 1.0)
    record_mapped(table, "_h", 25.0)
    record_mapped(table, "_missing")

    record_security_event("authz_fail", reason="staff_role_missing")
    record_mcp_security_event("mcp_output_blocked", tool_name="get_balance", namespace="ledger")
    record_mcp_security_event("unknown_mcp_kind", tool_name="get_balance")
    record_http_security_event(method="GET", status_code=200, route="/healthz")

    assert normalise_route("/staff/cases/7d1c0e2a-1b2c-4d5e?tab=1") == "/staff/cases/:id"
    assert normalise_route("a/b/c/d/e") == "/a/b/c"
    assert normalise_route("") == "/"
    assert route_label_from_scope({}) == "__unmatched__"

    batch = WebVitalsBatch(
        metrics=[
            WebVital(
                name="LCP", value=1400.0, rating="good", route="/en", navigation_type="navigate"
            ),
            WebVital(
                name="CLS", value=0.02, rating="good", route="/ar", navigation_type="navigate"
            ),
        ]
    )
    assert record_web_vitals(batch) == 2
    record_client_error(
        ClientError(
            kind="boundary", name="TypeError", digest="dig_01", source="app.js?v=1", route="/pga"
        )
    )

    with pytest.raises(ValueError):
        build_turn_audit_record(
            message="How much is PAYE on 250,000 SSP?",
            reply="Estimated monthly PAYE is 25,000 SSP.",
            channel="web",
            locale="en",
        )

    audit_rec = build_turn_audit_record(
        message="How much is PAYE on 250,000 SSP?",
        reply="Estimated monthly PAYE is 25,000 SSP.",
        channel="web",
        locale="en",
        locale_source="default",
        retrieval_mode="calculator",
        tool_calls=[
            {
                "name": "calculate_paye_estimate",
                "iteration": 1,
                "arguments": {"gross_monthly_ssp": "250000"},
            }
        ],
        citations=[
            {
                "doc_id": "doc_1",
                "section": "Sec-18",
                "title": "Taxation Act",
                "snippet": "PAYE schedule",
            }
        ],
        input_tokens=24,
        output_tokens=32,
        audit_hmac_key=b"test-audit-hmac-secret-key-32bytes",
    )
    assert audit_rec["schema"] == 2
    assert len(audit_rec["question_sha256"]) == 64
    assert len(audit_rec["reply_sha256"]) == 64
    assert "250,000" not in json.dumps(audit_rec)

    with mock.patch.dict(os.environ, {"SSRA_AUDIT_HMAC_KEY": "env-audit-hmac-key"}):
        env_audit = build_turn_audit_record(
            message="TIN registration",
            reply="Use https://etax.nra.gov.ss/",
            channel="web",
            locale="en",
        )
        assert len(env_audit["question_sha256"]) == 64


def test_api_metrics_and_client_telemetry_endpoints() -> None:
    app = create_api_app()
    client = AsgiTestClient(app)
    token = "m" * 40

    with mock.patch.dict(
        os.environ, {"SSRA_RUNTIME_MODE": "reference", "SSRA_METRICS_TOKEN": token}
    ):
        ok_before_obs = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
        assert ok_before_obs.status_code == 200
        assert "ssra_qdrant_index_fresh" not in ok_before_obs.text

        record_qdrant_lifecycle_observation(
            index_fresh=True,
            index_drift=False,
            observed_at_epoch_seconds=1761350000.0,
        )
        ok = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
        assert ok.status_code == 200
        assert "text/plain" in ok.headers.get("content-type", "")
        assert "ssra_qdrant_index_fresh 1" in ok.text
        assert "ssra_qdrant_index_status_timestamp_seconds 1761350000.0" in ok.text

        key = 'security_events_total{event="authn_login_fail"}'
        before_authn = metrics.snapshot()["counters"].get(key, 0)
        denied = client.get("/metrics", headers={"Authorization": "Bearer wrong-token"})
        assert denied.status_code == 401
        after_authn = metrics.snapshot()["counters"].get(key, 0)
        assert after_authn - before_authn == 1

    with mock.patch.dict(
        os.environ,
        {"SSRA_RUNTIME_MODE": "reference", "SSRA_METRICS_TOKEN": "", "METRICS_TOKEN": ""},
    ):
        unconfigured = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
        assert unconfigured.status_code == 401

    with mock.patch.dict(os.environ, {"SSRA_RUNTIME_MODE": "reference"}):
        vitals_ok = client.post(
            "/v1/telemetry/vitals",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 1650,
                        "rating": "good",
                        "route": "/c/3f2a9b1c-aaaa-bbbb",
                        "navigation_type": "navigate",
                    },
                    {
                        "name": "CLS",
                        "value": 0.01,
                        "rating": "good",
                        "route": "/en",
                        "navigation_type": "navigate",
                    },
                ]
            },
        )
        assert vitals_ok.status_code == 204

        vitals_extra = client.post(
            "/v1/telemetry/vitals",
            json={
                "metrics": [{"name": "LCP", "value": 100, "rating": "good", "user_id": "tin_leak"}]
            },
        )
        assert vitals_extra.status_code == 422

        vitals_oversize = client.post(
            "/v1/telemetry/vitals",
            content=b"x" * 20_000,
            headers={"Content-Type": "text/plain"},
        )
        assert vitals_oversize.status_code == 413

        err_ok = client.post(
            "/v1/telemetry/errors",
            json={"kind": "boundary", "name": "TypeError", "digest": "123456", "route": "/en"},
        )
        assert err_ok.status_code == 204

        err_with_msg = client.post(
            "/v1/telemetry/errors",
            json={"kind": "error", "message": "taxpayer typed secret TIN"},
        )
        assert err_with_msg.status_code == 422


def _exported_metric_catalogue() -> set[str]:
    return {
        "ssra_http_requests_total",
        "ssra_http_errors_total",
        "ssra_http_request_duration_ms_bucket",
        "ssra_http_request_duration_ms_count",
        "ssra_http_request_duration_ms_sum",
        "ssra_chat_turns_total",
        "ssra_retrieval_mode_total",
        "ssra_chat_response_time_ms_bucket",
        "ssra_chat_response_time_ms_count",
        "ssra_chat_response_time_ms_sum",
        "ssra_faithfulness_score_bucket",
        "ssra_faithfulness_score_count",
        "ssra_faithfulness_score_sum",
        "ssra_language_decisions_total",
        "ssra_escalation_required_total",
        "ssra_security_events_total",
        "ssra_web_vitals_ms_bucket",
        "ssra_web_vitals_ms_count",
        "ssra_web_vitals_ms_sum",
        "ssra_web_vitals_cls_bucket",
        "ssra_web_vitals_cls_count",
        "ssra_web_vitals_cls_sum",
        "ssra_client_errors_total",
        "ssra_qdrant_index_fresh",
        "ssra_qdrant_index_drift",
        "ssra_qdrant_index_status_timestamp_seconds",
        "ssra_qdrant_rebuild_failed",
        "ssra_qdrant_rebuild_timestamp_seconds",
        "ssra_qdrant_backup_required",
        "ssra_qdrant_backup_failed",
        "ssra_qdrant_backup_timestamp_seconds",
        "ssra_qdrant_restore_drill_failed",
        "ssra_qdrant_restore_drill_timestamp_seconds",
    }


def _slug(heading: str) -> str:
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _markdown_anchors(md_path: Path) -> set[str]:
    return {
        _slug(line.lstrip("#"))
        for line in md_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }


def test_monitoring_configs_slo_alerts_and_dashboard_agree() -> None:
    catalogue = _exported_metric_catalogue()
    rec_doc = yaml.safe_load((OBS_DIR / "recording-rules.yml").read_text(encoding="utf-8"))
    alert_doc = yaml.safe_load((OBS_DIR / "alerting-rules.yml").read_text(encoding="utf-8"))
    rec_rules = [r for g in rec_doc["groups"] for r in g["rules"]]
    alert_rules = [r for g in alert_doc["groups"] for r in g["rules"]]
    recordings = {r["record"] for r in rec_rules}

    for rule in rec_rules + alert_rules:
        unknown = sorted(set(_SSRA_SERIES_RE.findall(rule["expr"])) - catalogue)
        assert not unknown, (
            f"{rule.get('record') or rule['alert']} references unknown series: {unknown}"
        )
        missing_rec = sorted(set(_SSRA_RECORDING_RE.findall(rule["expr"])) - recordings)
        assert not missing_rec, f"undefined recording rules: {missing_rec}"

    for alert in alert_rules:
        labels = alert.get("labels", {})
        notes = alert.get("annotations", {})
        assert labels.get("severity") in {"critical", "warning"}
        assert labels.get("team")
        for key in ("summary", "description", "runbook_url"):
            assert notes.get(key), f"{alert['alert']} missing {key}"
        url = str(notes["runbook_url"])
        assert url.startswith(REPO_URL), url
        rel_path, _, anchor = url[len(REPO_URL) :].partition("#")
        doc_path = ROOT / rel_path
        assert doc_path.is_file(), f"{alert['alert']}: runbook {rel_path} does not exist"
        if anchor:
            assert anchor in _markdown_anchors(doc_path), (
                f"{alert['alert']}: heading #{anchor} not found in {rel_path}"
            )

    # OpenSLO v1 objectives match multi-window burn-rate alert budgets
    slo_docs = [
        d
        for d in yaml.safe_load_all(
            (OBS_DIR / "slo" / "ssra-assist.openslo.yaml").read_text(encoding="utf-8")
        )
        if d
    ]
    targets = {
        d["metadata"]["name"]: d["spec"]["objectives"][0]["target"]
        for d in slo_docs
        if d["kind"] == "SLO"
    }
    assert targets == {"api-availability": 0.999, "chat-latency": 0.95}
    alerts_by_name = {a["alert"]: a["expr"] for a in alert_rules}
    assert "0.001" in alerts_by_name["SsraAvailabilityBudgetBurnFast"]
    assert "0.001" in alerts_by_name["SsraAvailabilityBudgetBurnSlow"]
    assert "0.05" in alerts_by_name["SsraChatLatencyBudgetBurnFast"]

    # Prometheus config & Alertmanager config
    prom_cfg = yaml.safe_load((OBS_DIR / "prometheus.yml").read_text(encoding="utf-8"))
    for rf in prom_cfg["rule_files"]:
        assert (OBS_DIR / rf).is_file(), rf
    assert prom_cfg["alerting"]["alertmanagers"][0]["static_configs"][0]["targets"] == [
        "alertmanager:9093"
    ]
    api_job = next(j for j in prom_cfg["scrape_configs"] if j["job_name"] == "ssra-api")
    assert api_job["authorization"]["credentials_file"].startswith("/run/secrets/")
    scraped_jobs = {j["job_name"] for j in prom_cfg["scrape_configs"]}
    for alert in alert_rules:
        for job in re.findall(r'job="([^"]+)"', alert["expr"]):
            assert job in scraped_jobs, f"{alert['alert']} watches unscraped job {job!r}"

    am_cfg = yaml.safe_load((OBS_DIR / "alertmanager.yml").read_text(encoding="utf-8"))
    receivers = {r["name"]: r for r in am_cfg["receivers"]}
    assert am_cfg["route"]["receiver"] in receivers
    assert receivers["ops-webhook"]["webhook_configs"][0]["url_file"].startswith("/run/secrets/")

    loki_cfg = yaml.safe_load((OBS_DIR / "loki.yaml").read_text(encoding="utf-8"))
    assert loki_cfg["limits_config"]["allow_structured_metadata"] is True
    bb_cfg = yaml.safe_load((OBS_DIR / "blackbox.yml").read_text(encoding="utf-8"))
    assert "http_2xx" in bb_cfg["modules"]

    # Grafana dashboard queries only real series and recording rules
    dashboard = json.loads(
        (OBS_DIR / "dashboards" / "ssra-cx-overview.json").read_text(encoding="utf-8")
    )
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            expr = target.get("expr", "")
            unknown_s = sorted(set(_SSRA_SERIES_RE.findall(expr)) - catalogue)
            assert not unknown_s, f"panel {panel['title']!r} queries unknown series {unknown_s}"
            missing_r = sorted(set(_SSRA_RECORDING_RE.findall(expr)) - recordings)
            assert not missing_r, (
                f"panel {panel['title']!r} queries undefined recording {missing_r}"
            )
