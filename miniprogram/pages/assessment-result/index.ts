import type { AssessmentResult } from '../../types/api'

Page({
  data: { result: null as AssessmentResult | null, error: '' },
  onLoad(query: Record<string, string>) { try { this.setData({ result: JSON.parse(decodeURIComponent(query.result ?? '')) as AssessmentResult }) } catch { this.setData({ error: '本次记录暂时无法展示，请稍后重试' }) } },
  support() { wx.navigateTo({ url: '/pages/support-resources/index' }) },
  history() { wx.navigateTo({ url: '/pages/history/index' }) },
  again() { wx.switchTab({ url: '/pages/assessment-center/index' }) },
})
