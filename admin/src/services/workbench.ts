import { z } from "zod";
import { taskSummarySchema } from "../schemas/api";

export const WORKBENCH_SECTIONS = [
  "needs_action",
  "waiting_other",
  "recent",
] as const;
export type WorkbenchSectionKey = (typeof WORKBENCH_SECTIONS)[number];
export type WorkbenchSectionTitle = "需要我处理" | "等待他人" | "最近处理";
export type TaskSummary = z.infer<typeof taskSummarySchema>;
export interface WorkbenchPage {
  items: TaskSummary[];
  next_cursor: string | null;
}
const pageSchema = z.object({
  items: z.array(taskSummarySchema),
  next_cursor: z.string().nullable().optional(),
});
const demoPage: WorkbenchPage = { items: [], next_cursor: null };

export async function fetchWorkbenchSection(
  section: WorkbenchSectionKey,
  cursor?: string | null,
  request: typeof fetch = fetch,
  accessToken?: string,
): Promise<WorkbenchPage> {
  const params = new URLSearchParams({ section });
  if (cursor) params.set("cursor", cursor);
  const response = await request(
    `/api/v1/admin/workbench?${params.toString()}`,
    {
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
    },
  );
  if (response.status === 404 || response.status === 501) return demoPage;
  if (!response.ok) throw new Error(`workbench_${response.status}`);
  const json: unknown = await response.json();
  const envelope = z
    .object({
      data: z.unknown().optional(),
      error: z.unknown().nullable().optional(),
    })
    .passthrough()
    .parse(json);
  if (envelope.error) throw new Error("workbench_api_error");
  const page = pageSchema.parse(envelope.data ?? json);
  return { items: page.items, next_cursor: page.next_cursor ?? null };
}

export function getEmptyWorkbench(): {
  title: WorkbenchSectionTitle;
  count: number;
}[] {
  return [
    { title: "需要我处理", count: 0 },
    { title: "等待他人", count: 0 },
    { title: "最近处理", count: 0 },
  ];
}
