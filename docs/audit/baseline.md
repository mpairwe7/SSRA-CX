# R0 Assurance Baseline

**Audit date:** 2026-10-22

**Audited commit:** 7ca1f26e83b08decf64eacf02af059b537e69db7

**Branch:** chore/r0-baseline-assurance

**Scope:** source, configuration, local automated gates, local reference-mode tests, and checked-in documentation. No production credentials, real taxpayer data, deployment, or external state were accessed.

**Status:** Baseline complete. Gate R0 was approved in the active project session on 2026-10-22, authorizing R1 remediation only.

## Evidence conditions

- The checked-in graph report was read before source exploration. It reports generation on 2026-10-16 and reconciliation with source on 2026-10-21. The graphify executable is not installed in this sandbox, so the graph could not be refreshed. This is recorded as AUD-013.
- The local shell resolved Node 20.20.0 while package metadata and CI require Node 24. The Taskfile injects a Node 24 path, but the local package commands still reported the Node 20 engine warning.
- Docker Compose reported version 2.28.1, then the local Docker CLI plugin panicked. Compose topology findings below therefore use static configuration evidence, not a rendered or running production-equivalent stack.
- A five-run flake assessment was not completed. The first forced rerun hit a sandbox-owned uv cache permission error; the cache-free retry did not return a trustworthy consolidated result. The existing suite passed once, but repeatability is not yet proven.

## Tool inventory

| Tool | Observed version or status | Audit use |
|---|---|---|
| Git | 2.34.1 | Commit and history evidence |
| Node | 20.20.0 locally; CI config selects 24 | Local reproducibility condition |
| pnpm | 9.15.9 | Package lint, typecheck, and tests |
| uv | 0.7.20 | Python tooling and tests |
| Task | 3.54.0 | Canonical local gates |
| Docker Compose | 2.28.1; plugin instability after version output | Static topology only |
| gitleaks | Available; build version not embedded | Working-tree and full-history scan |
| trivy | 0.69.3; local database dated 2026-10-06 | Not relied on for a current vulnerability conclusion |
| graphify, zizmor, cosign, syft, semgrep | Not installed | Unavailable controls are findings or audit limitations |

## Executed baseline gates

| Command | Result | Evidence captured |
|---|---|---|
| task gen | Passed | Contract, OpenAPI, corpus-manifest, SBOM, and provenance generation completed without tracked-output drift. |
| task lint | Passed | Ruff and formatting clean for 263 files; basedpyright reported zero errors; import-linter kept two contracts; schema validation covered 3 contracts and 33 MCP tools over 11 servers; OpenAPI check reported 32 paths and no breaking change; frontend budget check reported 20.38 KB gzip against a 120 KB limit. |
| task test | Passed | Python tests, four injected rule mutants killed, domain coverage 100.0%, overall Python coverage 98.0%, and nine package Vitest tasks passed. Some Turbo tasks were cache hits; this result is a baseline, not a flake study. |
| task eval | Passed | Eval and ASI01–ASI10 red-team suites passed; the reference report records p50 4.44 ms and p95 5.07 ms ASGI timing; the restore drill reported 0.1543 seconds, one restored event, and a verified audit chain. |
| gitleaks detect --redact --log-opts='--all' | Passed | 140 commits and 5.65 MB scanned with no finding. This is a manual R0 result; CI currently uses the working-tree-only form. |
| git log --all --name-only --format='' -- .github/workflows | Reviewed | Only .github/workflows/ci.yml appeared. No unexpected workflow was found in reachable history. |
| pnpm why next sharp react-server-dom-* | No served dependency found | Neither web nor console declares Next.js or sharp; their Dockerfiles run Node server.js. The stale Next config remains AUD-008. |
| Runtime-mode probe using uv run | Partially passed | Unset resolves to production; empty and unknown resolve to no mode; mixed-case reference resolves to reference. Automated tests cover unset and unknown, but not empty or mixed case. |

## CI and test inventory

The only GitHub Actions workflow runs on pull requests and pushes to main. Its sole job uses SHA-pinned actions, frozen pnpm and uv installs, then runs Taskfile generation, lint, test, and eval. A checked-in GitLab file exists, but no GitLab or Forgejo execution evidence was available.

| Assurance area | Current evidence | Status |
|---|---|---|
| Formatting, strict Python types, import boundaries, TypeScript types | task lint and CI invoke them | Proven locally |
| Contract and schema drift | Taskfile generation plus git diff in CI; OpenAPI and JSON Schema checks pass | Proven locally |
| Coverage and rule mutation | Enforced locally at 98% domain and overall; four injected rule mutants killed | Proven locally |
| Hypothesis property coverage | Hypothesis is installed and used for rules and numeric-provenance properties | Partial: inventory does not prove every money, rounding, or Africa/Juba deadline path |
| API fuzzing and route matrix | Reference-mode unit tests cover selected guards | Not proven: no Schemathesis and no generated all-route production/reference matrix |
| Browser UI assurance | Unit-level accessibility, RTL, low-data, offline, and BFF tests exist | Not proven: no browser runner evidence for public chat, sidebar/rail, or staff dashboards under 2G, RTL, offline, and keyboard flows |
| Eval launch thresholds | 600-item test asserts 100% numeric accuracy and at least 95% citation precision; CI runs full eval | Proven for the reference suite |
| Flake detection | One normal run passed | Not proven: required five-run evidence is absent |
| Secrets in reachable history | Manual full-history gitleaks scan passed | Proven for this scan; not enforced in CI |

## Hypothesis outcome

| Hypothesis | R0 result | Evidence | Related finding |
|---|---|---|---|
| H-01 durable LangGraph state | Confirmed gap | Conversation runtime constructs InMemorySaver and keeps pending state in dictionaries. | AUD-001 |
| H-02 governed egress in GPU profile | Confirmed gap | GPU runtime declares direct model and TTS URLs; profile lacks agentgateway. | AUD-002 |
| H-03 transactional outbox | Confirmed gap | API uses InMemoryOutboxBuffer; no database transaction and publisher wiring were found. | AUD-003 |
| H-04 durable consent | Confirmed gap | Consent preferences use a module dictionary and consent is staged only as a process-local event. | AUD-004 |
| H-05 fail-closed route coverage | Partially proven | Middleware defaults to 503 and targeted tests pass; an exhaustive route matrix is absent. | AUD-009 |
| H-06 fail-closed runtime mode | Partially proven | Default and unknown mode tests pass; empty and mixed-case coverage is absent. | AUD-009 |
| H-07 BFF identity stripping | Partially proven | Public BFF sanitizes body identity and denies direct v1 paths, but encoding/header fuzzing is not a browser or property suite. | AUD-009 |
| H-08 Compose replacement controls | Confirmed gap | General profile is substantially hardened; GPU profile has tag-pinned images, env files, and incomplete parity. | AUD-005 |
| H-09 Next.js advisory exposure | No served Next.js dependency; configuration is stale | Dockerfiles run Node server.js and package manifests omit Next.js; config still claims Next 16.3.8 with Cache Components. | AUD-008 |
| H-10 MCP end-to-end deployment | Confirmed gap | Gateway routes name 11 MCP servers, but neither Compose profile declares all 11 individual services. | AUD-010 |
| H-11 offline statutory UI data | New gap | Client package contains statutory literals; validation only checks a subset of drift conditions. | AUD-011 |

## Baseline conclusion

No S0 indication was found in the available source or reachable history. The application has strong local reference-mode test coverage and several fail-closed guards. It is not ready to be treated as an operational government system: durable state, transactional delivery, production topology, artifact verification, browser-flow assurance, and deployment evidence remain open. The authoritative disposition is the finding register and Gate R0 report.
