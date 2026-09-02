import { z } from "zod";

export const apiErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  retryable: z.boolean(),
  current_version: z.number().nullable().optional(),
});

export const apiEnvelopeSchema = z.object({
  request_id: z.string(),
  data: z.unknown().nullable(),
  error: apiErrorSchema.nullable(),
});

export const taskKindSchema = z.enum([
  "content_review",
  "safety_support",
  "identity_access",
  "followup",
]);
export const taskStateSchema = z.enum([
  "needs_action",
  "claimed",
  "waiting_other",
  "completed",
  "cancelled",
]);

export const taskSummarySchema = z.object({
  task_id: z.string(),
  task_kind: taskKindSchema,
  state: taskStateSchema,
  created_at: z.string(),
  updated_at: z.string(),
  assigned_admin_display: z.string().nullable().optional(),
  safe_summary: z.string(),
  object_version: z.number().int(),
});

export const workbenchSchema = z.object({
  needs_action: z.array(taskSummarySchema),
  waiting_other: z.array(taskSummarySchema),
  recent: z.array(taskSummarySchema),
});

export const taskFactSchema = z.object({
  label: z.string(),
  value: z.string(),
});

export const taskDetailSchema = z.object({
  task_id: z.string(),
  task_kind: taskKindSchema,
  state: taskStateSchema,
  object_version: z.number().int(),
  facts: z.array(taskFactSchema),
  redacted_content: z.string().nullable().optional(),
  allowed_actions: z.array(z.string()),
  records: z.array(taskFactSchema).default([]),
  environment_kind: z.enum(["demo", "authorized", "unconfigured"]),
});

export const auditEventSchema = z.object({
  request_id: z.string(),
  actor: z.string(),
  capability: z.string(),
  resource: z.string(),
  action: z.string(),
  data_scope: z.array(z.string()),
  outcome: z.enum(["success", "denied", "conflict", "failure"]),
  reason_code: z.string().nullable().optional(),
  occurred_at: z.string(),
  environment_kind: z.enum(["demo", "authorized", "unconfigured"]),
});

export const auditPageSchema = z.object({
  items: z.array(auditEventSchema),
  next_cursor: z.string().nullable().optional(),
});

export type ApiEnvelope = z.infer<typeof apiEnvelopeSchema>;
export type ApiError = z.infer<typeof apiErrorSchema>;
export type TaskSummary = z.infer<typeof taskSummarySchema>;
export type TaskDetail = z.infer<typeof taskDetailSchema>;
export type TaskKind = z.infer<typeof taskKindSchema>;
export type TaskState = z.infer<typeof taskStateSchema>;
export type AuditEvent = z.infer<typeof auditEventSchema>;
