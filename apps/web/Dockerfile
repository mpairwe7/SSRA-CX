# Hardened Node 24 Alpine Container for SSRA Assist Taxpayer Web PWA (CIS Docker Benchmark v1.7)
FROM node:24-alpine AS runtime

LABEL org.opencontainers.image.title="ssra-web" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN addgroup -g 10001 -S ssra && \
    adduser -u 10001 -S ssra -G ssra

WORKDIR /app
COPY --chown=10001:10001 package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY --chown=10001:10001 packages ./packages
COPY --chown=10001:10001 apps/web ./apps/web

USER 10001:10001
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
