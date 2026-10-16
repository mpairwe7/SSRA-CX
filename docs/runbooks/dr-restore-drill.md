# SSRA Assist — Quarterly Disaster Recovery (DR) & PITR Restore Drill Runbook (`docs/runbooks/dr-restore-drill.md`)

**Status:** v1.0  
**Date:** 2026-10-16  
**Targets (Section 13):** RPO ≤ 5 minutes | RTO ≤ 1 hour  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 13, 15, 16

---

## 1. Automated DR Restore Drill Verification

Run the automated DR restore and WORM audit-chain verification drill at any time via:

```bash
uv run python tools/run_dr_restore_drill.py
```

---

## 2. Production NCA Quarterly Restore Procedure

1. **Provision Secondary Site Cluster (`infra/k8s/overlays/dr/`):**
   - Apply Kustomize DR overlay on the secondary NCA Kubernetes cluster.
2. **CloudNativePG Point-in-Time Recovery (`infra/k8s/cnpg-cluster.yaml`):**
   - Bootstrap the standby `ssra-postgres18-ha` cluster from Barman S3 WAL archives (`s3://ssra-nca-backups/postgres18-wal`) to target recovery timestamp.
3. **Verify Hash-Chained Audit & Knowledge Snapshot Integrity:**
   - Call `GET /v1/admin/audit-verify` and `GET /v1/knowledge-admin/active-snapshot` on the restored `services/api` instance.
   - Run `task eval` against the restored stack to confirm 100% numeric provenance and citation precision before switching DNS/edge traffic.
