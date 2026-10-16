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
  if (req.durationMinutes <= 0 || req.durationMinutes > 60) {
    return { granted: false, reason: "JIT_DURATION_EXCEEDS_60M_CAP" };
  }
  return { granted: true };
}
