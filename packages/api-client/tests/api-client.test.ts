import { describe, expect, it } from "vitest";
import {
  ApiEndpointPaths,
  ConversationResponseSchema,
  OPENAPI_CONTRACT_SHA256,
} from "../src/index.js";

describe("@ssra/api-client generated OpenAPI 3.1 contract", () => {
  it("exposes committed OpenAPI 3.1 paths and Zod validators", () => {
    expect(OPENAPI_CONTRACT_SHA256).toHaveLength(64);
    expect(ApiEndpointPaths).toContain("/v1/conversations");
    expect(ApiEndpointPaths).toContain("/v1/knowledge-admin/active-snapshot");

    const parsed = ConversationResponseSchema.parse({
      id: "conv_01929540",
      channel: "web",
      locale: "en",
      auth_level: "ANONYMOUS",
      status: "ACTIVE",
    });
    expect(parsed.status).toBe("ACTIVE");
  });
});
