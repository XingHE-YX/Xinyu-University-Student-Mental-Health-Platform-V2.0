import { z } from "zod";

export const apiErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  retryable: z.boolean(),
});

export const apiEnvelopeSchema = z.object({
  request_id: z.string(),
  data: z.unknown().nullable(),
  error: apiErrorSchema.nullable(),
});
