import { defineStore } from "pinia";
import { reactive, toRefs } from "vue";
import {
  getInitialAdminSession,
  loadAdminMe,
  logoutAdmin,
  type AdminSessionSummary,
} from "@/services/adminAuth";

export const useAdminSessionStore = defineStore("adminSession", () => {
  const initial = getInitialAdminSession();
  const state = reactive({
    isAuthenticated: false,
    displayName: initial.displayName,
    capabilityLabel: initial.capabilityLabel,
    environmentKind: initial.environmentKind,
    accessToken: "",
    refreshToken: "",
    accessExpiresAt: "",
    refreshExpiresAt: "",
    sessionExpiresAt: "",
  });

  function setSession(session: AdminSessionSummary): void {
    state.isAuthenticated = true;
    state.displayName = session.displayName;
    state.capabilityLabel = session.capabilityLabel;
    state.environmentKind = session.environmentKind;
    state.accessToken = session.accessToken;
    state.refreshToken = session.refreshToken;
    state.accessExpiresAt = session.accessExpiresAt;
    state.refreshExpiresAt = session.refreshExpiresAt;
    state.sessionExpiresAt =
      session.sessionExpiresAt ?? session.accessExpiresAt;
  }

  async function hydrate(): Promise<boolean> {
    if (!state.accessToken) return false;
    try {
      const me = await loadAdminMe(state.accessToken);
      state.displayName = me.displayName;
      state.capabilityLabel = me.capabilityLabel;
      state.environmentKind = me.environmentKind;
      state.sessionExpiresAt = me.sessionExpiresAt ?? state.accessExpiresAt;
      state.isAuthenticated = true;
      return true;
    } catch {
      clear();
      return false;
    }
  }

  async function logout(): Promise<void> {
    if (state.accessToken)
      await logoutAdmin(state.accessToken).catch(() => undefined);
    clear();
  }

  function clear(): void {
    state.isAuthenticated = false;
    state.accessToken = "";
    state.refreshToken = "";
    state.accessExpiresAt = "";
    state.refreshExpiresAt = "";
    state.sessionExpiresAt = "";
  }

  return { ...toRefs(state), setSession, hydrate, logout, clear };
});
