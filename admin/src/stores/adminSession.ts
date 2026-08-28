import { defineStore } from "pinia";

export const useAdminSessionStore = defineStore("adminSession", {
  state: () => ({
    isAuthenticated: false,
    displayName: "心理健康中心工作人员",
    capabilityLabel: "超级管理员",
  }),
  actions: {
    clear(): void {
      this.isAuthenticated = false;
    },
  },
});
