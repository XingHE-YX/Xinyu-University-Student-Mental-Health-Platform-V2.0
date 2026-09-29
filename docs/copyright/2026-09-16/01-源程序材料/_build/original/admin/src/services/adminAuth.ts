import { z } from "zod";
import { request } from "@/services/apiClient";

const sessionSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  access_expires_at: z.string(),
  refresh_expires_at: z.string(),
  display_name: z.string(),
  capability_label: z.string(),
});

const meSchema = z.object({
  display_name: z.string(),
  capability_label: z.string(),
  session_expires_at: z.string(),
  environment_kind: z.enum(["demo", "authorized", "unconfigured"]),
});

export interface AdminSessionSummary {
  displayName: string;
  capabilityLabel: string;
  environmentKind: "demo" | "authorized" | "unconfigured";
  accessToken: string;
  refreshToken: string;
  accessExpiresAt: string;
  refreshExpiresAt: string;
  sessionExpiresAt?: string;
}

export const FIXED_ADMIN_LOGIN = "心理健康中心工作人员";
export const FIXED_ADMIN_CAPABILITY = "超级管理员";

export async function loginAdmin(
  password: string,
): Promise<AdminSessionSummary> {
  const result = await request(
    "/api/v1/admin/auth/login",
    { method: "POST", body: { login_name: FIXED_ADMIN_LOGIN, password } },
    (value) => sessionSchema.parse(value),
  );
  const session = toSession(result.data);
  const me = await loadAdminMe(session.accessToken);
  return { ...session, ...me };
}

export async function loadAdminMe(
  accessToken: string,
): Promise<
  Pick<
    AdminSessionSummary,
    "displayName" | "capabilityLabel" | "environmentKind" | "sessionExpiresAt"
  >
> {
  const result = await request(
    "/api/v1/admin/me",
    { token: accessToken },
    (value) => meSchema.parse(value),
  );
  return {
    displayName: result.data.display_name,
    capabilityLabel: result.data.capability_label,
    environmentKind: result.data.environment_kind,
    sessionExpiresAt: result.data.session_expires_at,
  };
}

export async function logoutAdmin(accessToken: string): Promise<void> {
  await request(
    "/api/v1/admin/auth/logout",
    { method: "POST", token: accessToken },
    (value) => z.object({ success: z.boolean() }).parse(value),
  );
}

function toSession(value: z.infer<typeof sessionSchema>): AdminSessionSummary {
  return {
    displayName: value.display_name,
    capabilityLabel: value.capability_label,
    environmentKind: "demo",
    accessToken: value.access_token,
    refreshToken: value.refresh_token,
    accessExpiresAt: value.access_expires_at,
    refreshExpiresAt: value.refresh_expires_at,
  };
}

export function getInitialAdminSession(): Pick<
  AdminSessionSummary,
  "displayName" | "capabilityLabel" | "environmentKind"
> {
  return {
    displayName: FIXED_ADMIN_LOGIN,
    capabilityLabel: FIXED_ADMIN_CAPABILITY,
    environmentKind: "demo",
  };
}
