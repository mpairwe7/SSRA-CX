/**
 * Next.js 16.3.8 Configuration for Taxpayer PWA (`apps/web/next.config.ts` — Section 9.1).
 * Self-hosted standalone container output + Cache Components enabled.
 */

export const nextConfig = {
  output: "standalone",
  reactCompiler: true,
  cacheComponents: true,
  poweredByHeader: false,
} as const;

export default nextConfig;
