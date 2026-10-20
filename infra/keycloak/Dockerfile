# Hardened Multi-Stage Keycloak 26.4.11 Container (Quarkus Pre-Built Optimized Image — CIS Docker Benchmark v1.7)
FROM quay.io/keycloak/keycloak:26.4.11@sha256:f8f53f5990775d2b3056f5d5e19538909887821b6064232d032a27a4d5014140 AS builder

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_CACHE=ispn \
    KC_FEATURES=passkeys,token-exchange-standard:v2,dpop

WORKDIR /opt/keycloak
RUN mkdir -p /opt/keycloak/data/tmp /opt/keycloak/data/import && \
    /opt/keycloak/bin/kc.sh build \
    --db=postgres \
    --health-enabled=true \
    --metrics-enabled=true \
    --cache=ispn \
    --features=passkeys,token-exchange-standard:v2,dpop

FROM quay.io/keycloak/keycloak:26.4.11@sha256:f8f53f5990775d2b3056f5d5e19538909887821b6064232d032a27a4d5014140 AS runtime

LABEL org.opencontainers.image.title="ssra-keycloak" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

COPY --from=builder --chown=10001:10001 /opt/keycloak/ /opt/keycloak/
COPY --chown=10001:10001 infra/keycloak/ssra-realm.json /opt/keycloak/data/import/ssra-realm.json

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_HTTP_ENABLED=true \
    KC_HTTP_MANAGEMENT_PORT=9000 \
    KC_PROXY_HEADERS=xforwarded \
    KC_CACHE=ispn \
    KC_FEATURES=passkeys,token-exchange-standard:v2,dpop \
    JAVA_OPTS_APPEND="-XX:MaxRAMPercentage=70.0 -Djava.security.egd=file:/dev/urandom"

USER 10001:10001
EXPOSE 8080 9000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD ["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/9000 && printf 'GET /health/ready HTTP/1.0\\r\\nHost: localhost\\r\\n\\r\\n' >&3 && grep -q '200' <&3"]
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--optimized", "--import-realm"]
