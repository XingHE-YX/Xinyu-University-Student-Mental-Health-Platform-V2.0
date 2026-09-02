import { acknowledgeSupportResources, fetchResources } from '../../services/assessment'
import type { SupportResource } from '../../types/api'

Page({
  data: { loading: true, error: '', context: 'ordinary' as 'ordinary' | 'safety', safetyState: '' as string, sessionId: '', resources: [] as SupportResource[] },
  onLoad(query: Record<string, string>) { this.setData({ context: query.context === 'safety' ? 'safety' : 'ordinary', safetyState: query.state ?? '', sessionId: query.sessionId ?? '' }) },
  onShow() { this.load() },
  async load() { this.setData({ loading: true, error: '' }); try { this.setData({ resources: await fetchResources(this.data.context) }); if (this.data.context === 'safety' && this.data.safetyState === 'uncertain' && this.data.sessionId) await acknowledgeSupportResources(this.data.sessionId) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '支持资源暂时不可用' }) } finally { this.setData({ loading: false }) } },
  call(event: WechatMiniprogram.BaseEvent) { const phone = (event.currentTarget as WechatMiniprogram.Target).dataset.phone as string; if (phone) wx.makePhoneCall({ phoneNumber: phone }) },
  backToAnswer() { wx.navigateBack({ delta: 1 }) },
})
