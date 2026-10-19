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
  /(?:\.\.|[/\\]|\.(?:exe|bat|cmd|sh|js|mjs|cjs|html|htm|svg|php|py)$)/i;

export function validateClientUpload(input: {
  readonly mimeType: string;
  readonly sizeBytes: number;
  readonly filename?: string;
}): { readonly accepted: boolean; readonly reason?: string } {
  if (input.filename !== undefined) {
    const cleanName = input.filename.trim();
    if (!cleanName || cleanName.length > 180 || FORBIDDEN_FILENAME_PATTERN.test(cleanName)) {
      return { accepted: false, reason: "UNSAFE_FILENAME" };
    }
  }
  if (!ALLOWED_MIME_TYPES.has(input.mimeType)) {
    return { accepted: false, reason: "UNSUPPORTED_MIME_TYPE" };
  }
  if (input.sizeBytes <= 0 || input.sizeBytes > MAX_COMPRESSED_UPLOAD_BYTES) {
    return { accepted: false, reason: "EXCEEDS_LOW_BANDWIDTH_2MB_CAP" };
  }
  return { accepted: true };
}
