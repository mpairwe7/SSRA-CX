# Phase R2-D Report: Accessible Public Chat Interaction

**Date:** 2026-10-23

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** The public-chat parts of AUD-018 and AUD-019 in `apps/web/server.js`. The staff-console parts remain for R2-F.

## Scope and evidence boundary

All evidence comes from rendered Chromium runs against loopback synthetic services. Automated checks cannot establish WCAG conformance or screen-reader compatibility. Manual testing with NVDA, JAWS, VoiceOver, and TalkBack is still required, and so is research with taxpayers who use assistive technology.

## What was wrong

| Area | Observed at the R2-C baseline |
|---|---|
| Announcements | The whole transcript was a `role="log"` live region, rewritten on every update. |
| Phones | The composer status (draft restored, not answered) was `display: none` at 640 px or less. |
| Widget semantics | The account popover used `role="menu"` without menu keyboard support, and Escape did not close it. Settings tabs had no arrow-key model, roving `tabindex`, or `aria-controls`. The "Settings" heading sat inside the `tablist`. `<h2>` headings sat directly inside `role="list"`. |
| Dialogs | Rename used `window.prompt`; delete and clear-all used `window.confirm`. Clearing from Settings ran without confirmation. The page behind custom dialogs stayed in the accessibility tree. |
| False affordances | `Ctrl+N` and `Ctrl+,` were shown but not implemented. Voice typing was labelled "Whisper-SALT". A green presence dot implied a signed-in or online account. |
| Contrast and themes | Light-theme offline text was 1.31:1. The default was always dark. There were no `forced-colors` rules, and labels were as small as 10.4 px. |
| Speech | `Listen` used the browser's default voice language for Arabic pages. |

## Implemented controls

- A separate `#chat-announcer` status region (`aria-live="polite"`, `aria-atomic="true"`) announces "Preparing an answer.", "Answer received. …" (truncated to 280 characters), and "Not answered. …". The transcript is a labelled region without `aria-live`. A long new reply scrolls to its start rather than past it.
- `#composer-hint` holds only status text and stays visible at every width. Keyboard tips are a separate element that hides at 640 px or less.
- The account panel uses the disclosure pattern: no `menu` roles, `aria-expanded` on the trigger, Escape closes it and returns focus, and it closes when focus leaves the footer.
- Settings follow the APG tabs pattern: vertical `tablist` that contains only tabs, roving `tabindex`, Up/Down/Left/Right/Home/End navigation with automatic activation, `aria-controls`, and a tabpanel labelled by the selected tab. Toggle buttons keep focus after they re-render.
- A modal stack sets `inert` on the app shell and on lower dialogs. Escape closes the top dialog, and focus returns to the control that opened it.
- An in-page dialog (`role="dialog"`, labelled and described) replaces `prompt` and `confirm`. Destructive confirmations focus Cancel. Clearing from Settings now asks first. The "Clear all" button was removed from the header to avoid accidental taps; the action stays in Settings → Privacy.
- Removed the false shortcut hints and the presence dot. Voice typing is described as browser speech recognition. After dictation, the status says "Check it before you send."
- Light-theme offline text is `#991B1B` (6.35:1). The theme follows `prefers-color-scheme` and `prefers-contrast: more` until the user chooses one. `forced-colors` mode gets borders on controls and `Highlight` focus. The smallest labels are now 12 px.
- `Listen` and auto-narration set `lang` to `en` or `ar` when the interface uses one of those languages.

## Standards and design references

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) SC 1.3.1, 1.4.3, 2.1.1, 2.4.3, 3.2.4, 4.1.2, and 4.1.3.
- WAI-ARIA APG [tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/), [disclosure](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/), and [modal dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) patterns.
- Practitioner guidance on streaming chat (keep the transcript out of the live region; announce state changes), as cited in [the frontend audit](../product/frontend-ux-audit-2026-10.md#standards-and-research-checked-on-2026-10-23). These are secondary sources and need screen-reader confirmation.
- `closedby` is not Baseline and Safari does not support it, so dismissal is handled explicitly.

## Validation

| Check | Result |
|---|---|
| New `tests/browser/public-chat-a11y.spec.ts` on the R2-C `server.js` | 8 of 8 failed, as intended |
| Full browser suite after R2-D | 20 of 20 passed |
| Existing R2-B assertions | One locator was scoped to the transcript, because the answer text now also appears in the announcer, and the account-panel role changed from `menuitem` to `button`. No assertion was removed. |
| Biome, frontend budget and a11y verifier, SAST/DAST pipeline | Passed |
| Served `/en` size (gzip) | 24,174 bytes after R2-C; 25,805 bytes after R2-D; budget 150 KB |

## Threat-model delta

No new data flow, dependency, or storage key. Removing the header "Clear all" button reduces accidental data loss on shared phones. `inert` behind dialogs also prevents pointer activation of background controls.

## Residual work

- Manual assistive-technology testing of the announcer wording and timing.
- R2-E: language honesty, AI disclosure, and low-bandwidth behaviour.
- R2-F: staff-console combobox, account menu, contrast, and descriptions.
