# ADR-020: Node BFF Reference Runtime and Deferred Next.js Adoption

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-22
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Medium
- **Related:** [ADR-010](./0010-nextjs-16-typescript-7-turborepo-and-biome.md), [ADR-011](./0011-low-bandwidth-taxpayer-pwa-and-service-worker.md), [AUD-008](../audit/findings.md#aud-008--s2--frontend-dependency-hygiene--nextjs-configuration-is-stale-and-advisory-posture-is-ambiguous)

## Context

`apps/web` and `apps/console` are served by their respective `server.js` Node HTTP/BFF entry points. Their package manifests do not declare Next.js, and the containers execute those Node servers directly. The previous `next.config.ts` files therefore configured a framework that was not part of the served dependency graph or the deployed container command. That mismatch made the advisory and patch posture ambiguous.

The local Taskfile activates the integrity-pinned pnpm release through Corepack. The declared engine is deliberately bounded to Node 24 (`>=24.0.0 <25.0.0`), the currently supported local range with bundled Corepack. A broad engine range would admit Node releases that cannot execute those Taskfile gates without a separately reviewed provisioner.

The application still needs the low-bandwidth, accessibility, locale, and browser-security outcomes described in the earlier frontend proposals. Those outcomes do not require asserting that an uninstalled framework is active.

## Decision

1. Treat `apps/web/server.js` and `apps/console/server.js` as the current runnable reference runtime and BFF boundary.
2. Remove stale Next.js configuration and environment settings from the application containers.
3. Bound local JavaScript gates to the Node 24 Corepack-compatible range until a reviewed package-manager provisioner replaces that assumption.
4. Enforce the runtime decision in `tools/verify_supply_chain_and_signatures.py`: the stale configuration files must remain absent, neither application manifest may declare `next`, each container must launch its Node BFF entry point, and the Node engine must stay in the Corepack-compatible range.
5. Keep ADR-010 and ADR-011 as deferred design records. A future framework adoption requires a separate decision that names the runtime and exact reviewed dependency version, applies the cooldown policy, updates the container build and verification suite, and records the new attack-surface review.

## Consequences

- Current security maintenance applies to the declared Node BFF, application dependencies, and container base images. It does not claim a served Next.js runtime.
- Node 25 and later require a separately reviewed Corepack provisioner or package-manager activation design before they can run the local Taskfile JavaScript gates.
- The frontend remains subject to the existing WCAG 2.2 AA, i18n, low-bandwidth, CSP, and fail-closed staff-preview requirements.
- Introducing Next.js later has medium reversal cost because it changes the build system, dependency attack surface, container behavior, and rendered application verification.

## Verification

The supply-chain verifier and its regression tests reject a reintroduced stale configuration or a `next` declaration without a corresponding runtime decision. Full task gates and CI verify the current Node BFF entry points.
