/**
 * Staff Omnichannel Takeover/Hand-Back Banner, Tier T3 Two-Officer Maker-Checker Card,
 * and Multilingual RTL Reply Composer Preview (`apps/console/src/staff-workbench.ts` — Sections 3.3, 4, 11).
 */

import { isLiveOfficer, type StaffRole } from "./roles-and-audit.js";

export type ConversationOwnershipStatus = "ACTIVE" | "STAFF_TAKEOVER" | "HANDED_BACK_TO_AI";

export interface TakeoverHandbackBannerView {
  readonly bannerRole: "region";
  readonly ownershipStatus: ConversationOwnershipStatus;
  readonly assignedStaffId: string | null;
  readonly canTakeover: boolean;
  readonly canHandback: boolean;
  readonly whatsappWindowOpen: boolean;
  readonly requiresTemplateForOutbound: boolean;
  readonly statusSummary: string;
}

/**
 * Build the omnichannel AI Takeover & Hand-Back header banner for a conversation in the Staff Inbox.
 */
export function buildTakeoverHandbackBannerView(params: {
  readonly role: StaffRole;
  readonly currentStaffId: string;
  readonly status: ConversationOwnershipStatus;
  readonly assignedStaffId: string | null;
  readonly channel: "web" | "whatsapp" | "sms" | "ussd" | "voice";
  readonly hoursSinceLastTaxpayerMessage?: number | undefined;
}): TakeoverHandbackBannerView {
  const liveOfficer = isLiveOfficer(params.role);
  const isTakenOver = params.status === "STAFF_TAKEOVER";
  const canTakeover = liveOfficer && !isTakenOver;
  const canHandback =
    liveOfficer &&
    isTakenOver &&
    (params.assignedStaffId === null || params.assignedStaffId === params.currentStaffId);

  const hours = params.hoursSinceLastTaxpayerMessage ?? 0;
  const whatsappWindowOpen = params.channel !== "whatsapp" || hours <= 24;
  const requiresTemplateForOutbound = params.channel === "whatsapp" && !whatsappWindowOpen;

  const statusSummary = isTakenOver
    ? `Handled live by officer ${params.assignedStaffId ?? params.currentStaffId}`
    : params.status === "HANDED_BACK_TO_AI"
      ? "Handed back to SSRA Assist AI with full context"
      : "Handled by SSRA Assist AI";

  return {
    bannerRole: "region",
    ownershipStatus: params.status,
    assignedStaffId: params.assignedStaffId,
    canTakeover,
    canHandback,
    whatsappWindowOpen,
    requiresTemplateForOutbound,
    statusSummary,
  };
}

export interface MakerCheckerCardView {
  readonly caseId: string;
  readonly actionType: string;
  readonly makerStaffId: string;
  readonly currentStaffId: string;
  readonly canApprove: boolean;
  readonly disabledReason: string | null;
}

/**
 * Build the Tier T3 Two-Officer Maker-Checker approval card view (`POST /v1/cases/{id}/maker-checker`),
 * disabling self-approval when `currentStaffId === makerStaffId` or when viewed by a read-only auditor.
 */
export function buildMakerCheckerCardView(params: {
  readonly caseId: string;
  readonly actionType: string;
  readonly makerStaffId: string;
  readonly currentStaffId: string;
  readonly role: StaffRole;
  readonly rationale: string;
}): MakerCheckerCardView {
  if (params.role === "ssra_auditor") {
    return {
      caseId: params.caseId,
      actionType: params.actionType,
      makerStaffId: params.makerStaffId,
      currentStaffId: params.currentStaffId,
      canApprove: false,
      disabledReason: "Auditors are read-only and cannot approve Tier T3 maker-checker actions.",
    };
  }
  if (params.makerStaffId === params.currentStaffId) {
    return {
      caseId: params.caseId,
      actionType: params.actionType,
      makerStaffId: params.makerStaffId,
      currentStaffId: params.currentStaffId,
      canApprove: false,
      disabledReason:
        "Two-officer maker-checker rule: the initiating officer cannot approve their own T3 request.",
    };
  }
  if (params.rationale.trim().length < 5) {
    return {
      caseId: params.caseId,
      actionType: params.actionType,
      makerStaffId: params.makerStaffId,
      currentStaffId: params.currentStaffId,
      canApprove: false,
      disabledReason: "Enter an approval rationale (at least 5 characters) before approving.",
    };
  }
  return {
    caseId: params.caseId,
    actionType: params.actionType,
    makerStaffId: params.makerStaffId,
    currentStaffId: params.currentStaffId,
    canApprove: true,
    disabledReason: null,
  };
}

export interface StaffReplyComposerPreview {
  readonly locale: string;
  readonly dir: "ltr" | "rtl";
  readonly charCount: number;
  readonly estimatedSmsSegments: number;
  readonly hasOfficialPortalLink: boolean;
}

/**
 * Compute RTL text direction, character count, and SMS segment estimate (160 GSM-7 vs 70 Arabic UCS-2)
 * for the Staff Console reply composer.
 */
export function buildStaffReplyComposerPreview(params: {
  readonly draftText: string;
  readonly locale: string;
}): StaffReplyComposerPreview {
  const dir = params.locale === "ar" ? "rtl" : "ltr";
  const text = params.draftText.trim();
  const charCount = text.length;
  const hasNonAscii = /[^\x20-\x7E\n\r]/.test(text);
  const singleLimit = hasNonAscii ? 70 : 160;
  const concatLimit = hasNonAscii ? 67 : 153;
  const estimatedSmsSegments =
    charCount === 0 ? 0 : charCount <= singleLimit ? 1 : Math.ceil(charCount / concatLimit);

  return {
    locale: params.locale,
    dir,
    charCount,
    estimatedSmsSegments,
    hasOfficialPortalLink: text.includes("https://etax.nra.gov.ss/"),
  };
}
