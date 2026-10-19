/**
 * Staff Device Posture Check & Just-In-Time (JIT) Admin Elevation (`apps/console/src/jit-admin.ts` — Section 4 & 12.3).
 *
 * Enforces:
 * 1. Managed device posture (`diskEncrypted`, `edrActive`, `osPatchCurrent`).
 * 2. WebAuthn passkey verification.
 * 3. Maker-checker approval (`approverStaffId !== requesterStaffId`).
 * 4. Time-boxed JIT elevation (`durationMinutes <= 60`).
 */

export interface StaffDevicePosture {
  readonly deviceId: string;
  readonly diskEncrypted: boolean;
  readonly edrActive: boolean;
  readonly osPatchCurrent: boolean;
}

export interface JitAdminRequest {
  readonly requesterStaffId: string;
  readonly approverStaffId: string;
  readonly passkeyVerified: boolean;
  readonly devicePosture: StaffDevicePosture;
  readonly durationMinutes: number;
  readonly reason: string;
}

/**
 * Evaluate a Just-In-Time (JIT) Admin Elevation request against WebAuthn passkey,
 * managed device posture, two-officer maker-checker, integer duration, and rationale rules.
 */
export function evaluateJitAdminElevation(req: JitAdminRequest): {
  readonly granted: boolean;
  readonly reason?: string;
} {
  if (!req.passkeyVerified) {
    return { granted: false, reason: "WEBAUTHN_PASSKEY_REQUIRED" };
  }
  const p = req.devicePosture;
  if (!p.diskEncrypted || !p.edrActive || !p.osPatchCurrent) {
    return { granted: false, reason: "DEVICE_POSTURE_NON_COMPLIANT" };
  }
  if (!req.approverStaffId || req.approverStaffId === req.requesterStaffId) {
    return { granted: false, reason: "MAKER_CHECKER_APPROVAL_REQUIRED" };
  }
  if (
    !Number.isInteger(req.durationMinutes) ||
    req.durationMinutes <= 0 ||
    req.durationMinutes > 60
  ) {
    return { granted: false, reason: "JIT_DURATION_EXCEEDS_60M_CAP" };
  }
  if (!req.reason || req.reason.trim().length < 5) {
    return { granted: false, reason: "JIT_REASON_TOO_SHORT" };
  }
  return { granted: true };
}

export interface JitElevationBannerView {
  readonly state: "ACTIVE" | "EXPIRING_SOON" | "EXPIRED";
  readonly remainingSeconds: number;
  readonly mutationsUnlocked: boolean;
  readonly bannerRole: "status" | "alert";
  readonly countdownLabel: string;
}

/**
 * Build the time-boxed JIT Admin Elevation countdown banner (`<= 60` minutes, auto-revoking at `0s`).
 */
export function buildJitElevationBannerView(params: {
  readonly grantedAtMs: number;
  readonly durationMinutes: number;
  readonly nowMs: number;
}): JitElevationBannerView {
  const expiresAtMs = params.grantedAtMs + Math.max(0, params.durationMinutes) * 60_000;
  const remainingSeconds = Math.max(0, Math.floor((expiresAtMs - params.nowMs) / 1000));
  if (remainingSeconds === 0) {
    return {
      state: "EXPIRED",
      remainingSeconds: 0,
      mutationsUnlocked: false,
      bannerRole: "alert",
      countdownLabel:
        "JIT admin elevation expired — re-verify passkey & maker-checker to mutate flags",
    };
  }
  const mins = Math.floor(remainingSeconds / 60);
  const secs = remainingSeconds % 60;
  const expiringSoon = remainingSeconds <= 300;
  return {
    state: expiringSoon ? "EXPIRING_SOON" : "ACTIVE",
    remainingSeconds,
    mutationsUnlocked: true,
    bannerRole: expiringSoon ? "alert" : "status",
    countdownLabel: `JIT admin active (${mins}m ${secs}s remaining)`,
  };
}
