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
}

export interface AltchaSolution {
  readonly algorithm: "SHA-256";
  readonly challenge: string;
  readonly number: number;
  readonly salt: string;
  readonly signature: string;
}

async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function createAltchaChallenge(
  secretNumber: number,
  salt: string,
  hmacSecret: string,
  maxnumber = 5000,
): Promise<AltchaChallenge> {
  const challenge = await sha256Hex(`${salt}:${secretNumber}`);
  const signature = await sha256Hex(`${hmacSecret}:${challenge}`);
  return {
    algorithm: "SHA-256",
    challenge,
    maxnumber,
    salt,
    signature,
  };
}

export async function verifyAltchaSolution(
  solution: AltchaSolution,
  hmacSecret: string,
  maxnumber = 5000,
): Promise<boolean> {
  if (
    solution.algorithm !== "SHA-256" ||
    !Number.isSafeInteger(solution.number) ||
    solution.number < 0 ||
    solution.number > maxnumber
  ) {
    return false;
  }
  const recomputedChallenge = await sha256Hex(`${solution.salt}:${solution.number}`);
  if (recomputedChallenge !== solution.challenge) {
    return false;
  }
  const expectedSig = await sha256Hex(`${hmacSecret}:${solution.challenge}`);
  return expectedSig === solution.signature;
}
