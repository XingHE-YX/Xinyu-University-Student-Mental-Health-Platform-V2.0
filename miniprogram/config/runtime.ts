/** Non-secret values supplied by the WeChat external configuration. */

export type RuntimeEnvironmentKind = 'demo' | 'authorized' | 'unconfigured'

export interface RuntimeConfig {
  apiBaseUrl: string
  cloudbaseEnvId: string
  environmentKind: RuntimeEnvironmentKind
}

const isEnvironmentKind = (value: unknown): value is RuntimeEnvironmentKind =>
  value === 'demo' || value === 'authorized' || value === 'unconfigured'

const readExternalConfig = (): Record<string, unknown> => {
  if (typeof wx.getExtConfigSync !== 'function') return {}
  try {
    const value = wx.getExtConfigSync()
    return value && typeof value === 'object' ? value as Record<string, unknown> : {}
  } catch {
    return {}
  }
}

const external = readExternalConfig()
const apiBaseUrl = typeof external.apiBaseUrl === 'string' ? external.apiBaseUrl.trim() : ''
const cloudbaseEnvId = typeof external.cloudbaseEnvId === 'string' ? external.cloudbaseEnvId.trim() : ''
const environmentKind = isEnvironmentKind(external.environmentKind)
  ? external.environmentKind
  : 'unconfigured'

export const runtimeConfig: RuntimeConfig = {
  apiBaseUrl: /^https:\/\/[^\s]+\/api\/v1\/?$/.test(apiBaseUrl) ? apiBaseUrl.replace(/\/$/, '') : '',
  cloudbaseEnvId,
  environmentKind,
}
