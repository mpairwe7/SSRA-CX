# Phase R2-F Report: Staff Console Preview Accessibility and Truthfulness

**Date:** 2026-10-23

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** The staff-console parts of AUD-018 and AUD-019, and AUD-023, in `packages/ui/ops-console.js`.

## Scope and evidence boundary

The staff console remains a non-operational preview under ADR-018. Nothing in this phase adds staff identity, data, or actions; OQ-013 and OQ-014 still gate them. All evidence comes from rendered Chromium runs against the loopback preview server.

## What was wrong

| Finding | Observed at the R2-E baseline |
|---|---|
| AUD-018 | The command-palette input had no `combobox` role, `aria-expanded`, `aria-controls`, or `aria-activedescendant`, and its options had no IDs or `aria-selected`. Arrow keys moved a visual highlight that screen readers could not perceive. The account menu declared `role="menu"` but did not move focus into the menu or support arrow keys or Escape. Its headings were `role="presentation"` children of the menu. |
| AUD-019 | In the light theme, the "Preview only" chip was `#F4C430` on white (1.64:1). The "Preview only · no authenticated staff session" pill used the success colour. |
| AUD-023 | Destination `blurb` strings described "live calls, transfers & takeover", flags "served right now", and "Merkle seal proof". They were never rendered, so they were dead data. Main content was rendered only by script. |

## Implemented controls

- **Combobox.** `role="combobox"`, `aria-expanded="true"`, `aria-controls="cmdk-list"`, `aria-autocomplete="list"`, and `aria-activedescendant` that follows the active option. Options have stable IDs and `aria-selected`. A polite status announces the result count, including "No matching destinations". The active option scrolls into view, and the staff shell is inert while the palette is open.
- **Menu button.** Opening moves focus to the first item. Arrow keys, Home, and End move between items; Escape closes the menu and returns focus to the trigger; Tab closes it. The trigger opens the menu with ArrowDown or ArrowUp. Radio items sit in labelled `group`s, and the visible headings are `aria-hidden`. Persona commands in the palette persist the same preference as the menu.
- **Colour.** The preview chip uses the theme accent (`#704B00` in the light theme, 7.79:1 on white). The preview status pill uses the warning colour. The unused `.ops-preview-banner` rule was removed.
- **Server-rendered truth.** The destination list moved to module scope without the unused descriptions. The server renders the preview card, route heading, and page title. Client navigation updates only the heading and title, which removes a client-side HTML template. The route attribute is HTML-escaped.

## Standards and design references

- [WAI-ARIA APG combobox](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/) and [menu button](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/) patterns.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) SC 1.4.1, 1.4.3, 2.1.1, 4.1.2, and 4.1.3.
- Master prompt invariant 10 and ADR-018.

## Validation

| Check | Result |
|---|---|
| New `tests/browser/staff-console-a11y.spec.ts` on the R2-E `ops-console.js` | 4 of 4 failed, as intended |
| Full browser suite after R2-F | 30 of 30 passed |
| Existing staff spec | The palette input is now located by its `combobox` role instead of `textbox`. No assertion was removed. |
| Biome, frontend verifier, SAST/DAST pipeline, `apps/console` and `packages/ui` Vitest | Passed |

## Threat-model delta

No new route, data, or dependency. The preview is now legible without script, which reduces the chance that a blank or partially rendered page is mistaken for an operational console.

## Residual work

- Staff identity, authorization, and provenance-bearing data (OQ-013, OQ-014).
- Manual screen-reader testing of the palette and menu.
- Biome's `files.includes` covers `apps/**` and `packages/**` only, so `tests/browser/` is not linted. This predates this audit; widening it is a separate change.
