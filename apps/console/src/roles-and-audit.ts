/**
 * 3 Role-Based Dashboards (`ssra_staff`, `ssra_admin`, `ssra_auditor`),
 * Officer Call Desk (`calls/page.tsx` & `CallWorkspace.tsx`), and
 * Auditor WORM Audit Trail & Merkle Seal Inspector (`admin/audit/page.tsx`).
 */

export const STAFF_ROLES = ["ssra_staff", "ssra_admin", "ssra_auditor"] as const;
export type StaffRole = (typeof STAFF_ROLES)[number];

const STAFF_ROLE_SET: ReadonlySet<string> = new Set(STAFF_ROLES);

export function isStaffRole(role: string | undefined | null): boolean {
  return Boolean(role && STAFF_ROLE_SET.has(role));
}

export const ROLE_LABEL: Record<string, string> = {
  public: "Visitor",
  verified_taxpayer: "Taxpayer",
  ssra_staff: "Tax agent",
  ssra_admin: "Administrator",
  ssra_auditor: "Auditor",
};

export function roleLabel(role: string | undefined | null): string {
  if (!role) return "Visitor";
  return ROLE_LABEL[role] ?? role;
}

/**
 * Format a human-recognisable name for the signed-in officer: never display a raw
 * provider-prefixed OIDC subject (`keycloak|6a7d7af3ace1faccc70dc644`).
 */
export function signedInName(
  who:
    | { readonly email?: string; readonly external_id?: string; readonly role?: string }
    | null
    | undefined,
): string {
  if (!who) return "your account";
  if (who.email) return who.email;
  const id = who.external_id ?? "";
  if (!id) return "your account";
  const pipeIdx = id.indexOf("|");
  if (pipeIdx > 0 && pipeIdx < id.length - 1) {
    const tail = id.slice(pipeIdx + 1).slice(-6);
    return `${roleLabel(who.role)} · …${tail}`;
  }
  return id;
}

/**
 * Who handles taxpayers live (claims a case, replies, or takes a transferred phone call):
 * `ssra_staff` only. Administrators oversee operations; auditors inspect read-only.
 */
export function isLiveOfficer(role: string | undefined | null): boolean {
  return role === "ssra_staff";
}

/**
 * Who watches the live queue & call console bar: `ssra_staff` (works it) and
 * `ssra_auditor` (watches read-only). `ssra_admin` has no live queue bar.
 */
export function watchesLiveQueue(role: string | undefined | null): boolean {
  return role === "ssra_staff" || role === "ssra_auditor";
}

/**
 * Role-specific default dashboard landing path:
 * - `ssra_staff` -> `/agent` (Tax Agent Queue & Call Desk)
 * - `ssra_admin` -> `/admin` (Operations & Service Quality Overview)
 * - `ssra_auditor` -> `/analytics` (Analytics, Evaluation & WORM Audit Trail)
 */
export function staffLandingPath(
  role: string | undefined | null,
): "/agent" | "/admin" | "/analytics" {
  if (role === "ssra_staff") return "/agent";
  if (role === "ssra_auditor") return "/analytics";
  return "/admin";
}

export type StaffSection = "work" | "audit" | "configure" | "observe";

export interface StaffDestination {
  readonly href: string;
  readonly label: string;
  readonly navLabel: string;
  readonly group: StaffSection;
  readonly blurb: string;
  readonly roles: readonly StaffRole[];
}

export const STAFF_DESTINATIONS: readonly StaffDestination[] = [
  {
    href: "/admin",
    label: "Operations overview",
    navLabel: "Overview",
    group: "work",
    blurb: "Service levels, officers on duty, answer authority",
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/agent",
    label: "My queue",
    navLabel: "My queue",
    group: "work",
    blurb: "Claim a case and reply, one at a time",
    roles: ["ssra_staff"],
  },
  {
    href: "/admin/tickets",
    label: "All tickets",
    navLabel: "All tickets",
    group: "work",
    blurb: "Every escalation, every status, every team",
    roles: ["ssra_staff", "ssra_auditor"],
  },
  {
    href: "/calls",
    label: "Phone calls",
    navLabel: "Calls",
    group: "work",
    blurb: "AI phone receptionist: live calls, transfers, and officer audio takeover",
    roles: ["ssra_staff", "ssra_auditor"],
  },
  {
    href: "/admin/quality",
    label: "Service quality audit",
    navLabel: "Quality audit",
    group: "audit",
    blurb: "Where answers went wrong, from taxpayers' ratings",
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/flags",
    label: "Flags & kill switches",
    navLabel: "Flags",
    group: "configure",
    blurb: "Degradation ladder and feature flags this replica is serving right now",
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/discrepancies",
    label: "Knowledge & Bug Reports",
    navLabel: "Bug Reports",
    group: "configure",
    blurb: "Taxpayer-reported inaccuracies and knowledge discrepancies",
    roles: ["ssra_staff", "ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/overrides",
    label: "Answer overrides",
    navLabel: "Overrides",
    group: "configure",
    blurb: "Exact-match staff replies for known questions",
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/outbox",
    label: "Notification outbox",
    navLabel: "Outbox",
    group: "configure",
    blurb: "Queued WhatsApp, SMS, and email rows",
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/connectors",
    label: "System connectors",
    navLabel: "Connectors",
    group: "configure",
    blurb: "Health and enablement for e-Tax, e-Customs, and BoSS connectors",
    roles: ["ssra_staff", "ssra_admin"],
  },
  {
    href: "/analytics",
    label: "Analytics",
    navLabel: "Analytics",
    group: "observe",
    blurb: "SLOs, containment funnel, and regional language insights",
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/analytics/evaluation",
    label: "Answer evaluation",
    navLabel: "Evaluation",
    group: "observe",
    blurb: "600-item golden suite, groundedness, and ASI01-ASI10 red-team gates",
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/audit",
    label: "Audit trail",
    navLabel: "Audit trail",
    group: "audit",
    blurb: "Hash-chained WORM ledger verification and Merkle seals",
    roles: ["ssra_admin", "ssra_auditor"],
  },
];

export function staffDestinationsFor(role: string | undefined | null): StaffDestination[] {
  if (!role || !isStaffRole(role)) return [];
  return STAFF_DESTINATIONS.filter((d) => (d.roles as readonly string[]).includes(role));
}

export type CallDeskTab = "desk" | "callbacks" | "history" | "performance";
export type CallWorkspaceState =
  | "mine"
  | "wrap_up"
  | "waiting"
  | "claimed"
  | "ai"
  | "officer"
  | "ended";

/**
 * Officer Call Desk & Workspace (`calls/page.tsx` & `CallWorkspace.tsx` §3.3):
 * Officers (`ssra_staff`) take calls in `waiting` state; nobody steps into a call
 * the AI is still handling (`ai`), and auditors (`ssra_auditor`) watch read-only.
 */
export function resolveCallWorkspaceState(params: {
  readonly role: StaffRole;
  readonly callStatus: "ai" | "transferring" | "bridged" | "ended";
  readonly claimedByOfficer: string | null;
  readonly isMyActiveCall: boolean;
  readonly isWrapUpPending: boolean;
}): {
  readonly state: CallWorkspaceState;
  readonly canTakeCall: boolean;
  readonly deskDockSuppressed: true;
} {
  let state: CallWorkspaceState;
  if (params.isWrapUpPending) {
    state = "wrap_up";
  } else if (params.isMyActiveCall) {
    state = "mine";
  } else if (params.callStatus === "ended") {
    state = "ended";
  } else if (params.callStatus === "transferring") {
    state = params.claimedByOfficer ? "claimed" : "waiting";
  } else if (params.callStatus === "bridged") {
    state = "officer";
  } else {
    state = "ai";
  }

  return {
    state,
    canTakeCall: isLiveOfficer(params.role) && state === "waiting",
    deskDockSuppressed: true,
  };
}

export interface AuditBreakItem {
  readonly seq: number;
  readonly reason: string;
}

export interface AuditSealBreakItem {
  readonly first_seq: number;
  readonly last_seq: number;
  readonly reason: string;
}

export interface AuditVerificationReport {
  readonly valid: boolean;
  readonly head_hash: string;
  readonly unsealed_rows: number;
  readonly breaks: readonly AuditBreakItem[];
  readonly anchor_breaks: readonly AuditSealBreakItem[];
}

/**
 * Auditor WORM Audit Trail & Merkle Seal Inspector (`admin/audit/page.tsx`):
 * Places integrity verification first and pauses `Seal now` (`sealButtonDisabled: true`)
 * whenever the chain fails verification so an altered record can never be sealed in place.
 */
export function buildAuditorTrailIntegrityView(data: AuditVerificationReport) {
  const shortHeadHash = data.head_hash ? `${data.head_hash.slice(0, 10)}…` : "—";
  if (!data.valid) {
    const first = data.breaks[0];
    const sealBreak = data.anchor_breaks[0];
    const explanation = first
      ? `Event #${first.seq} fails its check (${first.reason}). Everything from that event on cannot be relied on as evidence until the cause is found.`
      : sealBreak
        ? `Events #${sealBreak.first_seq} to #${sealBreak.last_seq} no longer match their recorded seal (${sealBreak.reason}).`
        : "One or more events fail their check.";
    return {
      bannerRole: "alert" as const,
      chipClass: "is-danger" as const,
      chipText: "Record altered" as const,
      headline: "The audit trail does not verify",
      explanation,
      shortHeadHash,
      sealButtonDisabled: true,
      sealPausedReason:
        "Sealing is paused until the break is explained: a new seal would fix the altered record in place.",
    };
  }
  return {
    bannerRole: "status" as const,
    chipClass: "is-good" as const,
    chipText: "Record intact" as const,
    headline: "Every event fingerprint and Merkle seal verified",
    explanation: `Latest fingerprint ${shortHeadHash}.`,
    shortHeadHash,
    sealButtonDisabled: data.unsealed_rows === 0,
    sealPausedReason: null,
  };
}
