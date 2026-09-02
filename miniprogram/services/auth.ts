import { request } from './http'
import { sessionStore } from '../stores/session'
import type { StudentSession, UserProjection } from '../types/api'

export const loginWithWechat = async (): Promise<StudentSession> => {
  const loginResult = await new Promise<WechatMiniprogram.LoginSuccessCallbackResult>((resolve, reject) => {
    wx.login({ success: resolve, fail: reject })
  }).catch(() => ({ code: 'demo-code' } as WechatMiniprogram.LoginSuccessCallbackResult))
  const result = await request<Record<string, unknown>>('/auth/wechat/session', { method: 'POST', data: { code: loginResult.code, client_version: 'xinyu-v2-miniprogram' } })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '暂时无法进入，请稍后重试')
  const data = result.data
  const session: StudentSession = { accessToken: String(data.access_token ?? data.accessToken ?? ''), expiresAt: String(data.access_expires_at ?? data.expiresAt ?? ''), identityVerified: data.identity_status === 'verified' || data.identityVerified === true, basicConsent: data.base_consent_status === 'accepted' || data.basicConsent === true, communityConsent: data.community_consent_status === 'accepted' || data.communityConsent === true, accountStatus: data.account_status === 'recovery' ? 'recovery' : 'active' }
  sessionStore.set(session)
  sessionStore.setUser({ displayName: null, accountStatus: session.accountStatus, recoveryUntil: null, basicConsent: session.basicConsent, communityConsent: session.communityConsent, identityVerified: session.identityVerified })
  return session
}

export const fetchUser = async (): Promise<UserProjection> => {
  const result = await request<Record<string, unknown>>('/me')
  if (result.error || !result.data) throw new Error(result.error?.message ?? '账户信息暂时不可用')
  const data = result.data
  const user: UserProjection = { displayName: ((data.anonymous_identity_summary as Record<string, unknown> | undefined)?.display_name as string | undefined) ?? (data.displayName as string | undefined) ?? null, accountStatus: data.account_status === 'recovery_pending' || data.accountStatus === 'recovery' ? 'recovery' : 'active', recoveryUntil: (data.recovery_deadline_at as string | null | undefined) ?? null, basicConsent: data.base_consent === 'accepted' || data.basicConsent === true, communityConsent: data.community_consent === 'accepted' || data.communityConsent === true, identityVerified: data.identity_status === 'verified' || data.identityVerified === true }
  sessionStore.setUser(user)
  return user
}

export const recordBasicConsent = async (): Promise<void> => {
  const result = await request('/consents/base', { method: 'POST', data: { document_version: 'v1', action: 'accepted' }, idempotencyKey: `basic-${Date.now()}` })
  if (result.error) throw new Error(result.error.message)
  const current = sessionStore.get()
  if (current) sessionStore.set({ ...current, basicConsent: true })
  sessionStore.setUser({ ...sessionStore.getUser(), basicConsent: true })
}

export const verifyIdentity = async (name: string, studentNumber: string): Promise<UserProjection> => {
  const idempotencyKey = `identity-${Date.now()}`
  const result = await request<Record<string, unknown>>('/identity/verifications', { method: 'POST', data: { student_name: name, student_number: studentNumber, client_request_key: idempotencyKey }, idempotencyKey })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '身份核验暂时不可用')
  const resultData = result.data
  const user: UserProjection = { displayName: sessionStore.getUser().displayName ?? '一片云', accountStatus: sessionStore.getUser().accountStatus, recoveryUntil: null, basicConsent: true, communityConsent: sessionStore.getUser().communityConsent, identityVerified: resultData.status === 'verified' || resultData.identityVerified === true || resultData.verification_status === 'verified' }
  sessionStore.setUser(user)
  const current = sessionStore.get()
  if (current) sessionStore.set({ ...current, identityVerified: user.identityVerified })
  return user
}

export const updateCommunityConsent = async (granted: boolean): Promise<UserProjection> => {
  const result = await request<Record<string, unknown>>('/consents/community', { method: 'POST', data: { document_version: 'v1', action: granted ? 'accepted' : 'withdrawn' }, idempotencyKey: `community-${Date.now()}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '同意状态暂时无法更新')
  const data = result.data
  const currentUser = sessionStore.getUser()
  const user: UserProjection = { ...currentUser, communityConsent: data.community_consent === 'accepted' || data.communityConsent === true || (data.ok === true && granted) }
  sessionStore.setUser(user)
  const currentSession = sessionStore.get()
  if (currentSession) sessionStore.set({ ...currentSession, communityConsent: granted })
  return user
}

export const stopAccount = async (): Promise<void> => {
  const result = await request('/account/stop', { method: 'POST', data: { confirmation_text: '停止使用', object_version: 1 }, idempotencyKey: `stop-${Date.now()}` })
  if (result.error) throw new Error(result.error.message)
  const current = sessionStore.get()
  if (current) sessionStore.set({ ...current, accountStatus: 'recovery' })
  sessionStore.setUser({ ...sessionStore.getUser(), accountStatus: 'recovery' })
}

export const recoverAccount = async (): Promise<void> => {
  const result = await request('/account/recover', { method: 'POST', data: { object_version: 1 }, idempotencyKey: `recover-${Date.now()}` })
  if (result.error) throw new Error(result.error.message)
  const current = sessionStore.get()
  if (current) sessionStore.set({ ...current, accountStatus: 'active' })
  sessionStore.setUser({ ...sessionStore.getUser(), accountStatus: 'active' })
}
