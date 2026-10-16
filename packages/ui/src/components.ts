/**
 * WCAG 2.2 AA & RTL-Aware Accessible UI Primitives, Officer Duty Hours & Roving Menu Navigation (`packages/ui/src/components.ts` — Section 9.3).
 */

import type { LocaleCode } from "@ssra/contracts";
import { getMessages } from "@ssra/i18n";
import { getHtmlLayoutProps, SSRA_DESIGN_TOKENS } from "./index.js";

export interface AccessibleBannerDescriptor {
  readonly role: "region";
  readonly ariaLabel: string;
  readonly lang: LocaleCode;
  readonly dir: "ltr" | "rtl";
  readonly minTouchTargetPx: number;
  readonly cashFreeNotice: string;
  readonly assistantDisclosure: string;
  readonly officialPortalUrl: "https://etax.nra.gov.ss/";
}

export function buildOfficialHeaderBanner(locale: LocaleCode): AccessibleBannerDescriptor {
  const layout = getHtmlLayoutProps(locale);
  const messages = getMessages(locale);
  return {
    role: "region",
    ariaLabel: messages.appTitle,
    lang: layout.lang,
    dir: layout.dir,
    minTouchTargetPx: SSRA_DESIGN_TOKENS.minTouchTargetPx,
    cashFreeNotice: messages.cashFreeBanner,
    assistantDisclosure: messages.assistantDisclosure,
    officialPortalUrl: "https://etax.nra.gov.ss/",
  };
}

export interface AccessibleOtpInputDescriptor {
  readonly type: "text";
  readonly inputMode: "numeric";
  readonly autoComplete: "one-time-code";
  readonly dir: "ltr";
  readonly lang: LocaleCode;
  readonly minHeightPx: number;
  readonly focusOutlineCss: string;
  readonly pasteAllowed: true;
}

/**
 * WCAG 2.2 AA SC 3.3.8 (Accessible Authentication): OTP inputs must allow paste
 * and browser/SMS `one-time-code` autofill with LTR numeric direction even in RTL Arabic.
 */
export function buildAccessibleOtpInputProps(locale: LocaleCode): AccessibleOtpInputDescriptor {
  return {
    type: "text",
    inputMode: "numeric",
    autoComplete: "one-time-code",
    dir: "ltr",
    lang: locale,
    minHeightPx: SSRA_DESIGN_TOKENS.minTouchTargetPx,
    focusOutlineCss: SSRA_DESIGN_TOKENS.focusOutlineCss,
    pasteAllowed: true,
  };
}

export interface OfficerDutyHours {
  readonly onDuty: boolean;
  readonly hours: string;
  readonly nextOnDuty: string | null;
}

export function formatNextShiftJuba(iso: string, locale: LocaleCode): string | null {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return null;
  try {
    return new Intl.DateTimeFormat([locale, "en-SS", "en-GB"], {
      weekday: "long",
      day: "numeric",
      month: "long",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZone: "Africa/Juba",
      timeZoneName: "short",
    }).format(when);
  } catch {
    return null;
  }
}

export function extractOfficerHours(meta: Record<string, unknown>): OfficerDutyHours | undefined {
  const handoff = meta.handoff as Record<string, unknown> | null | undefined;
  const raw = (meta.officer_hours ??
    (handoff && typeof handoff === "object" ? handoff.officer_hours : undefined)) as
    | Record<string, unknown>
    | null
    | undefined;
  if (!raw || typeof raw !== "object") return undefined;
  const onDuty = raw.on_duty ?? raw.onDuty;
  if (typeof onDuty !== "boolean" || typeof raw.hours !== "string") return undefined;
  const next = raw.next_on_duty ?? raw.nextOnDuty;
  return {
    onDuty,
    hours: raw.hours.slice(0, 64),
    nextOnDuty: typeof next === "string" ? next : null,
  };
}

export interface MenuKeyNavigationOutcome {
  readonly nextIndex: number;
  readonly closeAndRestoreFocus: boolean;
  readonly handled: boolean;
}

/**
 * WCAG 2.2 AA Account Rail & Language Menu keyboard navigation (`ArrowDown`, `ArrowUp`, `Home`, `End`, `Escape`).
 */
export function resolveMenuKeyNavigation(
  key: string,
  currentIndex: number,
  itemCount: number,
): MenuKeyNavigationOutcome {
  if (itemCount <= 0) {
    return { nextIndex: 0, closeAndRestoreFocus: key === "Escape", handled: key === "Escape" };
  }
  const safeIndex = Math.max(0, Math.min(currentIndex, itemCount - 1));
  switch (key) {
    case "ArrowDown":
      return {
        nextIndex: (safeIndex + 1) % itemCount,
        closeAndRestoreFocus: false,
        handled: true,
      };
    case "ArrowUp":
      return {
        nextIndex: (safeIndex - 1 + itemCount) % itemCount,
        closeAndRestoreFocus: false,
        handled: true,
      };
    case "Home":
      return { nextIndex: 0, closeAndRestoreFocus: false, handled: true };
    case "End":
      return { nextIndex: itemCount - 1, closeAndRestoreFocus: false, handled: true };
    case "Escape":
      return { nextIndex: safeIndex, closeAndRestoreFocus: true, handled: true };
    default:
      return { nextIndex: safeIndex, closeAndRestoreFocus: false, handled: false };
  }
}
