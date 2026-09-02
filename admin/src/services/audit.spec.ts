import { describe, expect, it } from "vitest";
import {
  filterAuditEvents,
  getAuditEvents,
  resetDemoData,
  type AuditEvent,
} from "./audit";

const events: AuditEvent[] = [
  {
    id: "a1",
    occurredAt: "2026-08-30T10:00:00Z",
    eventType: "登录",
    objectId: "session-1",
    capability: "系统维护",
    result: "成功",
    mode: "演示模式",
    actor: "心理健康中心工作人员",
    action: "登录",
    rationale: "演示入口",
    fields: "会话",
    requestId: "req-1",
  },
  {
    id: "a2",
    occurredAt: "2026-08-31T10:00:00Z",
    eventType: "公开",
    objectId: "post-demo-01",
    capability: "内容审核",
    result: "成功",
    mode: "演示模式",
    actor: "心理健康中心工作人员",
    action: "公开帖子",
    rationale: "内容符合规则",
    fields: "公开状态",
    requestId: "req-2",
  },
];

describe("audit service", () => {
  it("filters by event type, result, mode and object id with pagination", () => {
    const result = filterAuditEvents(
      events,
      { eventType: "公开", result: "全部", mode: "演示模式", objectId: "post" },
      1,
      1,
    );
    expect(result.total).toBe(1);
    expect(result.items[0]?.id).toBe("a2");
  });

  it("rejects reset requests in authorized environments before any request", async () => {
    await expect(
      resetDemoData({ environment: "授权环境", namespace: "demo" }),
    ).rejects.toMatchObject({ code: "REAL_ENVIRONMENT_REJECTED" });
  });

  it("does not expose demo audit entries in an authorized environment", async () => {
    const result = await getAuditEvents(
      { eventType: "全部", result: "全部", mode: "全部", objectId: "" },
      1,
      10,
      "authorized",
    );
    expect(result.items).toEqual([]);
  });
});
