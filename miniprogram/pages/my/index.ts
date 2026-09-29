import { fetchProfile } from '../../services/me'
import { logoutSession } from '../../services/auth'
import type { UserProjection } from '../../types/api'

Page({
  data: { loading: true, loggingOut: false, error: '', profile: null as UserProjection | null },
  onShow() { this.load() },
  async load() { try { this.setData({ loading: true, error: '' }); this.setData({ profile: await fetchProfile() }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '账户信息暂时不可用' }) } finally { this.setData({ loading: false }) } },
  open(event: WechatMiniprogram.BaseEvent) { const path = (event.currentTarget as WechatMiniprogram.Target).dataset.path as string; wx.navigateTo({ url: path }) },
  async logout() {
    if (this.data.loggingOut) return
    this.setData({ loggingOut: true })
    try { await logoutSession() }
    finally { wx.reLaunch({ url: '/pages/onboarding/index' }) }
  },
})
