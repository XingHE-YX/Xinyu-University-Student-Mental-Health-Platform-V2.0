import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("versioned API configuration", () => {
  it("accepts the v2 base and rejects the obsolete v1 base", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://example.test/api/v2/");
    const v2 = await import("./runtime");
    expect(v2.adminRuntime.apiBaseUrl).toBe("https://example.test/api/v2");
    vi.resetModules();
    vi.stubEnv("VITE_API_BASE_URL", "https://example.test/api/v1");
    const v1 = await import("./runtime");
    expect(v1.adminRuntime.apiBaseUrl).toBe("");
  });
});
