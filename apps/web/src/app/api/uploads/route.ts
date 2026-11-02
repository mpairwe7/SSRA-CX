/**
 * BFF Compressed Upload Pre-Check Route (`apps/web/src/app/api/uploads/route.ts` — Section 9.3, 11, 16).
 */

const ALLOWED_MIME_TYPES = new Set([
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/avif",
]);

const MAX_COMPRESSED_UPLOAD_BYTES = 2 * 1024 * 1024; // 2 MB low-bandwidth cap on web chat
const FORBIDDEN_FILENAME_PATTERN =
  /(?:\.\.|[/\\]|\.(?:exe|bat|cmd|sh|js|mjs|cjs|html|htm|svg|php|py|xlsm|docm|pptm|xls)(?:\.|$))/i;
const BIDI_ONLY_RE = /[\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/;

function hasBidiOrControlChar(raw: string): boolean {
  if (BIDI_ONLY_RE.test(raw)) return true;
  for (let i = 0; i < raw.length; i += 1) {
    const code = raw.charCodeAt(i);
    if (code < 32 || code === 127) return true;
  }
  return false;
}

function verifyMagicBytesForMime(mimeType: string, bytes: Uint8Array): boolean {
  if (bytes.byteLength < 4) return false;
  if (mimeType === "application/pdf") {
    let off = 0;
    while (
      off < Math.min(bytes.byteLength, 8) &&
      (bytes[off] === 0x20 || bytes[off] === 0x09 || bytes[off] === 0x0d || bytes[off] === 0x0a)
    ) {
      off += 1;
    }
    return (
      bytes.byteLength >= off + 5 &&
      bytes[off] === 0x25 &&
      bytes[off + 1] === 0x50 &&
      bytes[off + 2] === 0x44 &&
      bytes[off + 3] === 0x46 &&
      bytes[off + 4] === 0x2d
    );
  }
  if (mimeType === "image/jpeg") {
    return bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  }
  if (mimeType === "image/png") {
    return (
      bytes.byteLength >= 8 &&
      bytes[0] === 0x89 &&
      bytes[1] === 0x50 &&
      bytes[2] === 0x4e &&
      bytes[3] === 0x47 &&
      bytes[4] === 0x0d &&
      bytes[5] === 0x0a &&
      bytes[6] === 0x1a &&
      bytes[7] === 0x0a
    );
  }
  if (mimeType === "image/webp") {
    return (
      bytes.byteLength >= 12 &&
      bytes[0] === 0x52 &&
      bytes[1] === 0x49 &&
      bytes[2] === 0x46 &&
      bytes[3] === 0x46 &&
      bytes[8] === 0x57 &&
      bytes[9] === 0x45 &&
      bytes[10] === 0x42 &&
      bytes[11] === 0x50
    );
  }
  if (mimeType === "image/avif") {
    return (
      bytes.byteLength >= 12 &&
      bytes[4] === 0x66 &&
      bytes[5] === 0x74 &&
      bytes[6] === 0x79 &&
      bytes[7] === 0x70 &&
      bytes[8] === 0x61 &&
      bytes[9] === 0x76 &&
      bytes[10] === 0x69 &&
      (bytes[11] === 0x66 || bytes[11] === 0x73)
    );
  }
  return false;
}

function hasEmbeddedActiveScriptTag(bytes: Uint8Array): boolean {
  const sample = new TextDecoder("latin1")
    .decode(bytes.subarray(0, Math.min(bytes.byteLength, 4096)))
    .toLowerCase();
  return sample.includes("<script") || sample.includes("<?php");
}

/**
 * Validate client upload MIME type, 2 MB low-bandwidth size cap, BiDi/double-extension filename grammar, and optional magic bytes.
 */
export function validateClientUpload(input: {
  readonly mimeType: string;
  readonly sizeBytes: number;
  readonly filename?: string;
  readonly magicBytes?: Uint8Array;
}): { readonly accepted: boolean; readonly reason?: string } {
  if (input.filename !== undefined) {
    const cleanName = input.filename.trim();
    if (
      !cleanName ||
      cleanName.length > 180 ||
      hasBidiOrControlChar(input.filename) ||
      FORBIDDEN_FILENAME_PATTERN.test(cleanName)
    ) {
      return { accepted: false, reason: "UNSAFE_FILENAME" };
    }
  }
  if (!ALLOWED_MIME_TYPES.has(input.mimeType)) {
    return { accepted: false, reason: "UNSUPPORTED_MIME_TYPE" };
  }
  if (input.sizeBytes <= 0 || input.sizeBytes > MAX_COMPRESSED_UPLOAD_BYTES) {
    return { accepted: false, reason: "EXCEEDS_LOW_BANDWIDTH_2MB_CAP" };
  }
  if (
    input.magicBytes !== undefined &&
    (!verifyMagicBytesForMime(input.mimeType, input.magicBytes) ||
      hasEmbeddedActiveScriptTag(input.magicBytes))
  ) {
    return { accepted: false, reason: "MAGIC_BYTE_MIME_MISMATCH" };
  }
  return { accepted: true };
}
