export type AuditMode = "演示模式" | "授权模式";
export type AuditEvent = {
  id: string;
  occurredAt: string;
  eventType: string;
  objectId: string;
  capability: string;
  result: string;
  mode: AuditMode;
  actor: string;
  action: string;
  rationale: string;
  fields: string;
  requestId: string;
  modelVersion?: string;
  promptVersion?: string;
};

export type AuditFilters = {
  from?: string;
  to?: string;
  eventType: string;
  result: string;
  mode: "全部" | AuditMode;
  objectId: string;
};
export type AuditPage = {
  items: AuditEvent[];
  total: number;
  page: number;
  pageSize: number;
  requestId: string;
};
export type ResetRequest = {
  environment: "演示环境" | "授权环境";
  namespace: string;
};
export type ResetCollectionResult = {
  collection: string;
  success: boolean;
  message?: string;
};
export type ResetResult = {
  success: boolean;
  requestId: string;
  collections: ResetCollectionResult[];
};

export class AuditServiceError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "AuditServiceError";
  }
}

export const demoAuditEvents: AuditEvent[] = [
  {
    id: "audit-001",
    occurredAt: "2026-08-31T09:30:00+08:00",
    eventType: "登录",
    objectId: "session-demo",
    capability: "系统维护",
    result: "成功",
    mode: "演示模式",
    actor: "心理健康中心工作人员",
    action: "进入演示后台",
    rationale: "固定演示入口",
    fields: "会话状态",
    requestId: "req-demo-001",
  },
  {
    id: "audit-002",
    occurredAt: "2026-08-31T10:05:00+08:00",
    eventType: "公开",
    objectId: "post-demo-01",
    capability: "内容审核",
    result: "成功",
    mode: "演示模式",
    actor: "心理健康中心工作人员",
    action: "公开内容",
    rationale: "内容符合公开规则",
    fields: "公开状态",
    requestId: "req-demo-002",
  },
  {
    id: "audit-003",
    occurredAt: "2026-08-31T10:18:00+08:00",
    eventType: "授权",
    objectId: "identity-demo-01",
    capability: "身份授权",
    result: "拒绝",
    mode: "演示模式",
    actor: "心理健康中心工作人员",
    action: "拒绝身份访问申请",
    rationale: "申请范围不足",
    fields: "授权状态",
    requestId: "req-demo-003",
  },
];

export function filterAuditEvents(
  source: AuditEvent[],
  filters: AuditFilters,
  page = 1,
  pageSize = 10,
): AuditPage {
  const filtered = source.filter(
    (event) =>
      (!filters.eventType ||
        filters.eventType === "全部" ||
        event.eventType === filters.eventType) &&
      (!filters.result ||
        filters.result === "全部" ||
        event.result === filters.result) &&
      (filters.mode === "全部" || event.mode === filters.mode) &&
      (!filters.objectId ||
        event.objectId
          .toLowerCase()
          .includes(filters.objectId.trim().toLowerCase())) &&
      (!filters.from || event.occurredAt.slice(0, 10) >= filters.from) &&
      (!filters.to || event.occurredAt.slice(0, 10) <= filters.to),
  );
  const safePage = Math.max(1, page);
  const start = (safePage - 1) * pageSize;
  return {
    items: filtered.slice(start, start + pageSize),
    total: filtered.length,
    page: safePage,
    pageSize,
    requestId: `req-audit-${Date.now()}`,
  };
}

export async function getAuditEvents(
  filters: AuditFilters,
  page = 1,
  pageSize = 10,
  environmentKind: "demo" | "authorized" | "unconfigured" = "demo",
): Promise<AuditPage> {
  if (environmentKind === "authorized") {
    return filterAuditEvents([], filters, page, pageSize);
  }
  return filterAuditEvents(demoAuditEvents, filters, page, pageSize);
}

export type CollectionResetter = (
  collection: string,
) => Promise<ResetCollectionResult>;
const demoCollections = [
  "tasks",
  "posts",
  "responses",
  "assessments",
  "identities",
  "safety_tasks",
  "audit",
];

export async function resetDemoData(
  request: ResetRequest,
  resetter?: CollectionResetter,
): Promise<ResetResult> {
  if (
    request.environment !== "演示环境" ||
    !request.namespace.startsWith("demo")
  )
    throw new AuditServiceError(
      "REAL_ENVIRONMENT_REJECTED",
      "真实环境不允许重置演示数据",
    );
  const collections = resetter
    ? await Promise.all(
        demoCollections.map(async (collection) => {
          try {
            return await resetter(collection);
          } catch {
            return {
              collection,
              success: false,
              message: "该数据域暂时没有完成重置",
            };
          }
        }),
      )
    : demoCollections.map((collection) => ({ collection, success: true }));
  return {
    success: collections.every((item) => item.success),
    requestId: `req-reset-${Date.now()}`,
    collections,
  };
}
