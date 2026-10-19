# Hardened Multi-Stage Keycloak 26.4.11 Container (Quarkus Pre-Built Optimized Image — CIS Docker Benchmark v1.7)
FROM quay.io/keycloak/keycloak:26.4.11 AS builder

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_FEATURES=passkeys,token-exchange-standard:v2

WORKDIR /opt/keycloak
RUN /opt/keycloak/bin/kc.sh build \
    --db=postgres \
    --health-enabled=true \
    --metrics-enabled=true \
    --features=passkeys,token-exchange-standard:v2

FROM quay.io/keycloak/keycloak:26.4.11 AS runtime

LABEL org.opencontainers.image.title="ssra-keycloak" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

COPY --from=builder --chown=10001:10001 /opt/keycloak/ /opt/keycloak/
COPY --chown=10001:10001 infra/keycloak/ssra-realm.json /opt/keycloak/data/import/ssra-realm.json

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_HTTP_ENABLED=true \
    KC_PROXY_HEADERS=xforwarded \
    KC_FEATURES=passkeys,token-exchange-standard:v2

USER 10001:10001
EXPOSE 8080 9000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD ["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/9000 && printf 'GET /health/ready HTTP/1.0\\r\\nHost: localhost\\r\\n\\r\\n' >&3 && grep -q '200' <&3"]
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--optimized", "--import-realm"]
