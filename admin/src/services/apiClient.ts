import { apiEnvelopeSchema } from "@/schemas/api";

export class AdminApiError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly currentVersion: number | null;
  readonly requestId: string | null;
  readonly status: number;

  constructor(
    message: string,
    options: {
      code?: string;
      retryable?: boolean;
      currentVersion?: number | null;
      requestId?: string | null;
      status?: number;
    } = {},
  ) {
    super(message);
    this.name = "AdminApiError";
    this.code = options.code ?? "INTERNAL_ERROR";
    this.retryable = options.retryable ?? false;
    this.currentVersion = options.currentVersion ?? null;
    this.requestId = options.requestId ?? null;
    this.status = options.status ?? 500;
  }
}

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export function createIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `admin-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function request<T>(
  path: string,
  options: {
    token?: string | null;
    method?: "GET" | "POST";
    body?: unknown;
    idempotent?: boolean;
    signal?: AbortSignal;
  } = {},
  parse: (value: unknown) => T,
): Promise<{ data: T; requestId: string }> {
  const headers = new Headers({ Accept: "application/json" });
  if (options.body !== undefined)
    headers.set("Content-Type", "application/json");
  if (options.token) headers.set("Authorization", `Bearer ${options.token}`);
  if (options.idempotent)
    headers.set("Idempotency-Key", createIdempotencyKey());

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch {
    throw new AdminApiError("暂时没有连接到服务，请重新尝试", {
      code: "DEPENDENCY_UNAVAILABLE",
      retryable: true,
      status: 503,
    });
  }

  const raw: unknown = await response.json().catch(() => null);
  const envelope = apiEnvelopeSchema.safeParse(raw);
  if (!envelope.success) {
    throw new AdminApiError("暂时没有加载到内容，请重新尝试", {
      code: "INTERNAL_ERROR",
      retryable: true,
      status: response.status,
    });
  }
  if (!response.ok || envelope.data.error) {
    const error = envelope.data.error;
    throw new AdminApiError(
      error?.message ?? "暂时没有完成这项操作，请重新尝试",
      {
        code: error?.code,
        retryable: error?.retryable,
        currentVersion: error?.current_version,
        requestId: envelope.data.request_id,
        status: response.status,
      },
    );
  }
  return {
    data: parse(envelope.data.data),
    requestId: envelope.data.request_id,
  };
}
