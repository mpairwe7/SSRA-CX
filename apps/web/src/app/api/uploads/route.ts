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

export function validateClientUpload(input: {
  readonly mimeType: string;
  readonly sizeBytes: number;
}): { readonly accepted: boolean; readonly reason?: string } {
  if (!ALLOWED_MIME_TYPES.has(input.mimeType)) {
    return { accepted: false, reason: "UNSUPPORTED_MIME_TYPE" };
  }
  if (input.sizeBytes <= 0 || input.sizeBytes > MAX_COMPRESSED_UPLOAD_BYTES) {
    return { accepted: false, reason: "EXCEEDS_LOW_BANDWIDTH_2MB_CAP" };
  }
  return { accepted: true };
}
