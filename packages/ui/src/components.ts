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

export interface NetworkInformationLike {
  readonly saveData?: boolean;
  readonly effectiveType?: string;
  readonly downlink?: number;
  readonly rtt?: number;
}

/**
 * ADR-011 2G Low-Data / Text-Only Mode detector from Network Information API or user preference.
 */
export function shouldEnableLowDataMode(
  connection?: NetworkInformationLike | null,
  userOverride?: boolean,
): boolean {
  if (userOverride !== undefined) {
    return userOverride;
  }
  if (!connection) {
    return false;
  }
  if (connection.saveData === true) {
    return true;
  }
  const eff = (connection.effectiveType ?? "").toLowerCase();
  if (eff === "slow-2g" || eff === "2g") {
    return true;
  }
  if (
    typeof connection.downlink === "number" &&
    connection.downlink > 0 &&
    connection.downlink < 0.5
  ) {
    return true;
  }
  if (typeof connection.rtt === "number" && connection.rtt > 1000) {
    return true;
  }
  return false;
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

export type ViewportBreakpoint = "xs_320" | "sm_mobile" | "md_tablet" | "lg_desktop";
export type PointerModality = "coarse" | "fine";

export interface ResponsiveViewportContext {
  readonly viewportWidthPx: number;
  readonly breakpoint: ViewportBreakpoint;
  readonly isMobileViewport: boolean;
  readonly reflowSafeAt320Px: true;
  readonly viewportHeightCss: "100dvh" | "100svh";
  readonly safeAreaBottomInsetCss: string;
  readonly safeAreaInlinePaddingCss: string;
  readonly containerQueryCss: "container-type: inline-size";
  readonly effectiveTouchTargetPx: number;
  readonly minTargetSpacingPx: number;
  readonly navigationPattern: "bottom_sheet_rail" | "collapsible_side_rail";
}

/**
 * Resolve October 2026 mobile responsiveness, WCAG 2.2 SC 1.4.10 Reflow (320px floor),
 * `100dvh`/`100svh` dynamic viewport units, `env(safe-area-inset-*)` notch padding,
 * `@container` inline-size queries, and coarse-pointer touch targets (`48px` vs `44px`).
 */
export function resolveResponsiveViewportContext(params: {
  readonly viewportWidthPx: number;
  readonly pointer?: PointerModality | undefined;
  readonly virtualKeyboardOpen?: boolean | undefined;
}): ResponsiveViewportContext {
  const width = Number.isFinite(params.viewportWidthPx)
    ? Math.max(320, Math.round(params.viewportWidthPx))
    : 375;
  const breakpoint: ViewportBreakpoint =
    width < 360 ? "xs_320" : width < 640 ? "sm_mobile" : width < 1024 ? "md_tablet" : "lg_desktop";
  const isMobileViewport = width < 768;
  const isCoarse = params.pointer === "coarse" || isMobileViewport;

  return {
    viewportWidthPx: width,
    breakpoint,
    isMobileViewport,
    reflowSafeAt320Px: true,
    viewportHeightCss: params.virtualKeyboardOpen ? "100svh" : "100dvh",
    safeAreaBottomInsetCss: "max(0.75rem, env(safe-area-inset-bottom, 0px))",
    safeAreaInlinePaddingCss:
      "max(1rem, env(safe-area-inset-left, 0px)) max(1rem, env(safe-area-inset-right, 0px))",
    containerQueryCss: "container-type: inline-size",
    effectiveTouchTargetPx: isCoarse
      ? SSRA_DESIGN_TOKENS.coarsePointerTouchTargetPx
      : SSRA_DESIGN_TOKENS.minTouchTargetPx,
    minTargetSpacingPx: SSRA_DESIGN_TOKENS.minTargetSpacingPx,
    navigationPattern: isMobileViewport ? "bottom_sheet_rail" : "collapsible_side_rail",
  };
}
