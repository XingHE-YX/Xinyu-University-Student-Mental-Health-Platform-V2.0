export interface AdminSessionSummary {
  displayName: string;
  capabilityLabel: string;
}

export function getInitialAdminSession(): AdminSessionSummary {
  return {
    displayName: "心理健康中心工作人员",
    capabilityLabel: "超级管理员",
  };
}
