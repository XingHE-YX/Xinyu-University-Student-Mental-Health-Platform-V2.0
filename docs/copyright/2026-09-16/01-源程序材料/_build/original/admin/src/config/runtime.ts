/** Build-time, non-secret values for the independently hosted admin SPA. */

export type AdminEnvironmentKind = "demo" | "authorized" | "unconfigured";

const rawApiBaseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const normalizedApiBaseUrl = rawApiBaseUrl.trim().replace(/\/$/, "");
const rawEnvironmentKind =
  (import.meta.env.VITE_ENVIRONMENT_KIND as string | undefined) ??
  "unconfigured";

export const adminRuntime = {
  apiBaseUrl: /^https:\/\/[^\s]+\/api\/v1$/.test(normalizedApiBaseUrl)
    ? normalizedApiBaseUrl
    : "",
  environmentKind: (rawEnvironmentKind === "demo" ||
  rawEnvironmentKind === "authorized" ||
  rawEnvironmentKind === "unconfigured"
    ? rawEnvironmentKind
    : "unconfigured") as AdminEnvironmentKind,
} as const;
