import { fetchHistory } from '../../services/me'
import type { HistoryItem } from '../../types/api'

Page({
  data: { loading: true, error: '', items: [] as HistoryItem[] },
  onShow() { this.load() },
  async load() { try { this.setData({ loading: true, error: '' }); this.setData({ items: await fetchHistory() }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '历史记录暂时不可用' }) } finally { this.setData({ loading: false }) } },
  start() { wx.switchTab({ url: '/pages/assessment-center/index' }) },
  open(event: WechatMiniprogram.BaseEvent) { const target = event.currentTarget as WechatMiniprogram.Target; const id = target.dataset.id as string; const category = target.dataset.category as string; wx.navigateTo({ url: `/pages/delete-confirmation/index?id=${id}&category=${category}` }) },
})
