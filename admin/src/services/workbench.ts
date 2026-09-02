import { z } from "zod";
import { taskSummarySchema } from "../schemas/api";
import { AdminApiError, request as apiRequest } from "@/services/apiClient";

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
  requestFn: typeof fetch = fetch,
  accessToken?: string,
): Promise<WorkbenchPage> {
  const params = new URLSearchParams({ section });
  if (cursor) params.set("cursor", cursor);
  try {
    const result = await apiRequest(
      `/api/v1/admin/workbench?${params.toString()}`,
      { token: accessToken, fetchImpl: requestFn },
      (value) => pageSchema.parse(value),
    );
    return {
      items: result.data.items,
      next_cursor: result.data.next_cursor ?? null,
    };
  } catch (error) {
    if (error instanceof AdminApiError && [404, 501].includes(error.status)) {
      return demoPage;
    }
    throw error;
  }
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
