export type DeploymentEnvironmentKind = 'demo' | 'authorized'

export interface DeploymentProfile {
  apiBaseUrl: string
  cloudbaseEnvId: string
  environmentKind: DeploymentEnvironmentKind
}

const profiles: Readonly<Record<string, DeploymentProfile>> = {
  wx22f399558d68bc7f: {
    apiBaseUrl:
      'https://xinyu-v2-demo-d3g8qbyfu11a452ff-1489915847.ap-shanghai.app.tcloudbase.com/api/v1',
    cloudbaseEnvId: 'xinyu-v2-demo-d3g8qbyfu11a452ff',
    environmentKind: 'demo',
  },
}

export const deploymentProfileForAppId = (appId: string): DeploymentProfile | null =>
  profiles[appId.trim()] ?? null
