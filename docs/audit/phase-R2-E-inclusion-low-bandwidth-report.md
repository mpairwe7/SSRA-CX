# Phase R2-E Report: Language Honesty, AI Disclosure, and Low Bandwidth

**Date:** 2026-10-23

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** AUD-020, AUD-021, and AUD-022 in `apps/web/server.js`, plus the compression setting in `apps/console/server.js`.

## Scope and evidence boundary

All evidence comes from rendered Chromium runs and local measurements against loopback synthetic services. No translation was written or changed. The disclosure wording is interim until SSRA Legal answers OQ-009 item 2. Low-end Android and real 2G measurements are still required.

## What was wrong

| Finding | Observed at the R2-D baseline |
|---|---|
| AUD-020 | Five Phase 4 locales shipped unreviewed interface strings, including script mixing (Arabic script inside Bari and Dinka text). `<html lang>` claimed those languages. The placeholder and a sample prompt advertised Dinka, which the Phase 1 evaluation set does not cover. |
| AUD-021 | No notice next to the composer said that answers are AI-generated and can be wrong, or warned against typing identifiers. Device storage was disclosed only inside Settings, in tier jargon (`T0`, `T1`, `T2`). |
| AUD-022 | Low-data mode changed only a request flag and badge text. There was no `<noscript>` path. `/healthz` returned internal service URLs. Brotli quality 4 produced a larger page than gzip. The status text "citations shown with answers" claimed something not every answer has. |

## Implemented controls

- **Reviewed locales only.** The interface dictionary keeps `en`, `pga`, and `ar`. The other five locales stay selectable under "Not yet reviewed (interface in English)". They render English text with `lang="en"` and `dir="ltr"` on both the server and the client, and a notice says that the language has not been reviewed or tested and names the checked languages. The placeholder and sample prompts match the evaluated set. The known `pga` string defect is recorded under OQ-008 item 3 for a qualified reviewer.
- **Disclosure.** A persistent line under the composer says: "SSRA Assist is an automated AI assistant and can make mistakes. Check answers against the cited sources. Don’t enter your TIN, phone number, or passwords in this public chat." It is marked `lang="en"` and recorded as interim wording under OQ-009 item 2.
- **Shared devices.** The rail states where conversations are kept. Settings → Privacy explains storage in plain language and can turn off device history, which empties stored conversations.
- **Low data.** `data-low-data` removes blur, decorative backgrounds, shadows, animations, and transitions. `prefers-reduced-transparency` removes the blur and decorative backgrounds.
- **Resilience and disclosure.** A `<noscript>` note points to the official e-Tax portal. `/healthz` returns only `status` and `service`. Connection status reads "Online", "Low-data mode · online", or "Offline". The web manifest gains `id`, `scope`, `lang`, `dir`, and a description.
- **Compression.** Brotli quality 5 with a size hint in both Node servers.

## Measurements

The served `/en` page is about 106 KB uncompressed. Times are the mean of 200 compressions in Node 24.16.

| Encoding | Bytes | Time |
|---|---:|---:|
| gzip level 6 | 25,809 | 1.44 ms |
| Brotli quality 4 (previous) | 26,011 | 1.26 ms |
| Brotli quality 5 (chosen) | 24,234 | 1.75 ms |
| Brotli quality 6 | 24,062 | 1.89 ms |
| Brotli quality 9 | 23,876 | 16.50 ms |

After R2-E, `/en` is 24,442 bytes with Brotli and 26,050 bytes with gzip. The staff preview is 13,891 bytes with Brotli and 14,610 bytes with gzip. Both decode correctly.

## Standards and design references

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) SC 3.1.1 (Language of Page) and SC 3.1.2 (Language of Parts).
- OQ-008 and OQ-009; master prompt invariant 2.
- [GOV.UK Chat app design (GDS, 19 August 2026)](https://insidegovuk.blog.gov.uk/2026/08/19/designing-gov-uk-chat-for-the-gov-uk-app/): "AI can make mistakes", check sources.
- EU AI Act Article 50(1), as a comparative benchmark only.
- [Chrome: `prefers-reduced-transparency`](https://developer.chrome.com/blog/css-prefers-reduced-transparency).
- OWASP ASVS v5.0.0 V13 (unintended information disclosure) for `/healthz`.

## Validation

| Check | Result |
|---|---|
| New `tests/browser/public-chat-inclusion.spec.ts` on the R2-D `server.js` | 6 of 6 failed, as intended |
| Full browser suite after R2-E | 26 of 26 passed |
| `apps/web` Vitest, Biome, frontend verifier, SAST/DAST pipeline | Passed |

## Threat-model delta

- **Removed:** internal service addresses in `/healthz`; interface text that a qualified reviewer had not approved; implied support for unevaluated languages.
- **Added:** a user-controlled option to keep conversations out of `localStorage`. It reduces stored data and adds no new storage.

## Residual work

- Reviewed translations of the interface and the disclosure for `pga`, `ar`, and Phase 4 locales (OQ-008, OQ-009).
- Device and network measurements on low-end Android and real 2G.
- R2-F: staff dashboards.
