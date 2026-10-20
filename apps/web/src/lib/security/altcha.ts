/**
 * Self-hosted ALTCHA Proof-of-Work Bot Defence for Public Chat (Section 9.4).
 * Zero third-party trackers or external CAPTCHA scripts.
 * Uses Web Crypto API (SubtleCrypto) available in standard ES2023 / Browser / Node 24+.
 */

export interface AltchaChallenge {
  readonly algorithm: "SHA-256";
  readonly challenge: string;
  readonly maxnumber: number;
  readonly salt: string;
  readonly signature: string;
  readonly expiresAt?: number;
}

export interface AltchaSolution {
  readonly algorithm: "SHA-256";
  readonly challenge: string;
  readonly number: number;
  readonly salt: string;
  readonly signature: string;
  readonly maxnumber?: number;
  readonly expiresAt?: number;
}

const MAX_SOLVED_CHALLENGES = 2048;
const solvedChallenges = new Map<string, number>();

/**
 * Constant-time string equality check to mitigate timing side-channels on HMAC signatures.
 */
function timingSafeEqualStr(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * Compute SHA-256 hex digest using Web Crypto SubtleCrypto.
 */
async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Compute HMAC-SHA-256 hex digest using Web Crypto SubtleCrypto.
 */
async function hmacSha256Hex(secret: string, input: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await globalThis.crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await globalThis.crypto.subtle.sign("HMAC", key, enc.encode(input));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Create a self-hosted ALTCHA SHA-256 proof-of-work challenge within `[0..maxnumber]`,
 * enforcing CVE-2025-68113 (`GHSA-6gvq-jcmp-8959`) parameter-delimiter binding.
 */
export async function createAltchaChallenge(
  secretNumber: number,
  salt: string,
  hmacSecret: string,
  maxnumber = 5000,
  expiresAt?: number,
): Promise<AltchaChallenge> {
  if (
    !Number.isSafeInteger(maxnumber) ||
    maxnumber < 1 ||
    !Number.isSafeInteger(secretNumber) ||
    secretNumber < 0 ||
    secretNumber > maxnumber ||
    !salt ||
    salt.includes(":")
  ) {
    throw new RangeError("secretNumber must be an integer within [0..maxnumber] with valid salt");
  }
  // CVE-2025-68113: Bind salt parameters unambiguously before the nonce delimiter
  const delimitedSalt = salt.endsWith("&") ? salt : `${salt}&`;
  const challenge = await sha256Hex(`${delimitedSalt}:${secretNumber}`);
  const expPart = expiresAt !== undefined ? String(expiresAt) : "noexp";
  const signature = await hmacSha256Hex(
    hmacSecret,
    `${delimitedSalt}:${maxnumber}:${expPart}:${challenge}`,
  );
  return {
    algorithm: "SHA-256",
    challenge,
    maxnumber,
    salt: delimitedSalt,
    signature,
    ...(expiresAt !== undefined ? { expiresAt } : {}),
  };
}

/**
 * Verify a client-submitted ALTCHA proof-of-work solution against its challenge, expiration, and HMAC signature.
 */
export async function verifyAltchaSolution(
  solution: AltchaSolution,
  hmacSecret: string,
  maxnumber = 5000,
  nowMs = Date.now(),
): Promise<boolean> {
  const solutionMax = solution.maxnumber ?? maxnumber;
  const effectiveMax = Math.min(maxnumber, solutionMax);
  if (
    solution.algorithm !== "SHA-256" ||
    !solution.salt ||
    !solution.salt.endsWith("&") ||
    solution.salt.includes(":") ||
    !Number.isSafeInteger(solutionMax) ||
    solutionMax < 1 ||
    !Number.isSafeInteger(solution.number) ||
    solution.number < 0 ||
    solution.number > effectiveMax
  ) {
    return false;
  }
  if (solution.expiresAt !== undefined && nowMs > solution.expiresAt) {
    return false;
  }
  const recomputedChallenge = await sha256Hex(`${solution.salt}:${solution.number}`);
  if (!timingSafeEqualStr(recomputedChallenge, solution.challenge)) {
    return false;
  }
  const expPart = solution.expiresAt !== undefined ? String(solution.expiresAt) : "noexp";
  const expectedSig = await hmacSha256Hex(
    hmacSecret,
    `${solution.salt}:${solutionMax}:${expPart}:${solution.challenge}`,
  );
  return timingSafeEqualStr(expectedSig, solution.signature);
}

/**
 * Verify and consume a single-use ALTCHA solution so solved challenges cannot be replayed (CVE-2025-68113).
 * Fails closed if `expiresAt` is missing or if the replay cache is full of unexpired entries.
 */
export async function consumeAltchaSolution(
  solution: AltchaSolution,
  hmacSecret: string,
  maxnumber = 5000,
  nowMs = Date.now(),
): Promise<boolean> {
  if (solution.expiresAt === undefined) {
    return false;
  }
  const ok = await verifyAltchaSolution(solution, hmacSecret, maxnumber, nowMs);
  if (!ok) {
    return false;
  }
  for (const [k, exp] of solvedChallenges.entries()) {
    if (nowMs > exp) {
      solvedChallenges.delete(k);
    }
  }
  const replayKey = `${solution.challenge}:${solution.signature}`;
  if (solvedChallenges.has(replayKey)) {
    return false;
  }
  if (solvedChallenges.size >= MAX_SOLVED_CHALLENGES) {
    return false;
  }
  solvedChallenges.set(replayKey, solution.expiresAt);
  return true;
}
