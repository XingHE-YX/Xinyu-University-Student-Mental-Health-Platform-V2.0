/** Non-secret values supplied by the WeChat external configuration. */
import { deploymentProfileForAppId } from './deployment-profiles'
import { localPreviewConfig } from './local-preview'

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

const readCurrentAppId = (): string => {
  try {
    return wx.getAccountInfoSync().miniProgram.appId?.trim() ?? ''
  } catch {
    return ''
  }
}

if (Object.keys(external).length === 0) {
  const deploymentProfile = deploymentProfileForAppId(readCurrentAppId())
  if (deploymentProfile) Object.assign(external, deploymentProfile)
}

try {
  if (Object.keys(external).length === 0 && localPreviewConfig.enabled && wx.getDeviceInfo().platform === 'devtools') {
    Object.assign(external, localPreviewConfig)
  }
} catch { /* Unsupported clients keep the explicit unconfigured state. */ }
const apiBaseUrl = typeof external.apiBaseUrl === 'string' ? external.apiBaseUrl.trim() : ''
const cloudbaseEnvId = typeof external.cloudbaseEnvId === 'string' ? external.cloudbaseEnvId.trim() : ''
const environmentKind = isEnvironmentKind(external.environmentKind)
  ? external.environmentKind
  : 'unconfigured'

const isLocalPreview = (): boolean => {
  try { return wx.getDeviceInfo().platform === 'devtools' && environmentKind === 'demo' }
  catch { return false }
}
const localApi = isLocalPreview() && /^http:\/\/127\.0\.0\.1:\d+\/api\/v1\/?$/.test(apiBaseUrl)

export const runtimeConfig: RuntimeConfig = {
  apiBaseUrl: /^https:\/\/[^\s]+\/api\/v1\/?$/.test(apiBaseUrl) || localApi ? apiBaseUrl.replace(/\/$/, '') : '',
  cloudbaseEnvId,
  environmentKind,
}
