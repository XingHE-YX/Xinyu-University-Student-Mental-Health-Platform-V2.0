import {
  taskDetailSchema,
  taskStateSchema,
  type TaskDetail,
} from "@/schemas/api";
import { z } from "zod";
import { request, type AdminApiError } from "@/services/apiClient";

export type TaskDecision =
  | {
      action: "publish" | "protect" | "unpublish" | "safety_review";
      internal_reason: string;
    }
  | {
      action: "record_support" | "set_followup" | "complete";
      fact_note: string;
      followup_due_at?: string;
    }
  | { action: "approve" | "deny" | "revoke" }
  | {
      action: "record_followup" | "complete";
      action_code: string;
      fact_note: string;
      next_due_at?: string;
    };

const mutationSchema = z.object({
  task_id: z.string(),
  new_state: taskStateSchema,
  new_object_version: z.number().int(),
  audit_request_id: z.string(),
});

export type TaskMutationResult = z.infer<typeof mutationSchema>;

export async function fetchTaskDetail(
  taskId: string,
  token?: string,
): Promise<TaskMutationResult> {
  const result = await request(
    `/api/v1/admin/tasks/${encodeURIComponent(taskId)}`,
    { token },
    (value) => mutationSchema.parse(value),
  );
  return result.data;
}

export async function claimTask(
  taskId: string,
  objectVersion: number,
  token?: string,
): Promise<TaskMutationResult> {
  const result = await request(
    `/api/v1/admin/tasks/${encodeURIComponent(taskId)}/claim`,
    {
      method: "POST",
      token,
      body: { object_version: objectVersion },
      idempotent: true,
    },
    (value) => mutationSchema.parse(value),
  );
  return result.data;
}

export async function releaseTask(
  taskId: string,
  objectVersion: number,
  token?: string,
): Promise<TaskMutationResult> {
  const result = await request(
    `/api/v1/admin/tasks/${encodeURIComponent(taskId)}/release`,
    {
      method: "POST",
      token,
      body: { object_version: objectVersion },
      idempotent: true,
    },
    (value) => mutationSchema.parse(value),
  );
  return result.data;
}

export async function decideTask(
  taskId: string,
  objectVersion: number,
  decision: TaskDecision,
  token?: string,
): Promise<TaskDetail> {
  const result = await request(
    `/api/v1/admin/tasks/${encodeURIComponent(taskId)}/decision`,
    {
      method: "POST",
      token,
      body: { ...decision, object_version: objectVersion },
      idempotent: true,
    },
    (value) => taskDetailSchema.parse(value),
  );
  return result.data;
}

export type TaskDetailError = AdminApiError;
