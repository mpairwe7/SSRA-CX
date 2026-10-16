/**
 * Next.js 16.3.8 Configuration for Staff Console (`apps/console/next.config.ts` — Section 9.1, 9.2).
 */

export const nextConfig = {
  output: "standalone",
  reactCompiler: true,
  poweredByHeader: false,
} as const;

export default nextConfig;
