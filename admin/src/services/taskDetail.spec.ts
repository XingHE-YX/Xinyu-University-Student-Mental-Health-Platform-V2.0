import { describe, expect, it, vi } from "vitest";
import { claimTask } from "./taskDetail";

describe("task detail actions", () => {
  it("sends the object version and a fresh idempotency key", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          request_id: "req-claim-1",
          data: {
            task_id: "task-1",
            new_state: "claimed",
            new_object_version: 2,
            audit_request_id: "req-audit-1",
          },
          error: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    vi.stubGlobal("fetch", fetcher);
    const result = await claimTask("task-1", 1, "access-token");

    expect(result.new_state).toBe("claimed");
    const [, init] = fetcher.mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(headers.get("Idempotency-Key")).toEqual(expect.any(String));
    expect(JSON.parse(String(init?.body))).toEqual({ object_version: 1 });
    vi.unstubAllGlobals();
  });
});
