# SSRA Assist — Quarterly Disaster Recovery (DR) & PITR Restore Drill Runbook (`docs/runbooks/dr-restore-drill.md`)

**Status:** v2.0 (Docker Compose 2026 Standardization)  
**Date:** 2026-10-17  
**Targets (Section 13):** RPO ≤ 5 minutes | RTO ≤ 1 hour  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 13, 15, 16

---

## 1. Automated DR Restore Drill Verification

Run the automated DR restore and WORM audit-chain verification drill at any time via:

```bash
uv run python tools/run_dr_restore_drill.py
```

---

## 2. Production NCA Quarterly Docker Compose Restore Procedure

1. **Provision Secondary NCA Host & Verify Signed Container Images (`infra/compose/docker-compose.prod.yml`):**
   - Verify Cosign image digests and the CycloneDX 1.6 Software + AI/ML-BOM (`infra/observability/cyclonedx-sbom.json`), then start the standby Docker Compose stack on the secondary NCA host:
     ```bash
     docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml --profile dr up -d --wait
     ```
2. **PostgreSQL 18 Point-in-Time Recovery (`postgres` + `postgres-wal-archiver`):**
   - Restore the latest base backup and replay WAL segments from `s3://ssra-nca-backups/postgres18-wal` up to `recovery_target_time` inside the `postgres` Docker Compose service (`RPO <= 5 min`, `RTO <= 1 h`).
3. **Verify Hash-Chained Audit & Knowledge Snapshot Integrity:**
   - Call `GET /v1/admin/audit-verify` and `GET /v1/knowledge-admin/active-snapshot` on the restored `api` container (`http://127.0.0.1:8000`).
   - Run `task eval` against the restored Docker Compose stack to confirm 100% numeric provenance and citation precision before switching DNS/edge traffic.
