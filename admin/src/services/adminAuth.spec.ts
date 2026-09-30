import { describe, expect, it, vi } from "vitest";
import { loginAdmin } from "./adminAuth";

describe("admin authentication URLs", () => {
  it("appends admin routes once to an API base ending in /api/v2", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "req-login",
            data: {
              access_token: "access-token",
              refresh_token: "refresh-token",
              access_expires_at: "2026-09-22T11:00:00Z",
              refresh_expires_at: "2026-09-22T18:00:00Z",
              display_name: "心理健康中心工作人员",
              capability_label: "超级管理员",
            },
            error: null,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "req-me",
            data: {
              display_name: "心理健康中心工作人员",
              capability_label: "超级管理员",
              session_expires_at: "2026-09-22T11:00:00Z",
              environment_kind: "demo",
            },
            error: null,
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetcher);

    await loginAdmin("correct-password");

    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      "/admin/auth/login",
      "/admin/me",
    ]);
    vi.unstubAllGlobals();
  });
});
