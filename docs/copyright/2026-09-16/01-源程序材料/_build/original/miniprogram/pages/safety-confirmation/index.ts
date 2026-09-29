import { confirmSafety } from '../../services/assessment'
import { assessmentStore } from '../../stores/assessment'

Page({
  data: { loading: false, error: '', sessionId: '', selected: '' },
  onLoad(query: Record<string, string>) { this.setData({ sessionId: query.sessionId ?? assessmentStore.get()?.sessionId ?? '' }) },
  async choose(event: WechatMiniprogram.BaseEvent) { const state = (event.currentTarget as WechatMiniprogram.Target).dataset.state as 'can_be_safe' | 'uncertain' | 'cannot_be_safe'; this.setData({ loading: true, error: '', selected: state }); try { const current = assessmentStore.get(); await confirmSafety(this.data.sessionId, state, current?.answers.slice(0, 9) ?? []); assessmentStore.setSafety(state); if (state === 'can_be_safe') wx.navigateBack(); else wx.redirectTo({ url: `/pages/support-resources/index?context=safety&state=${state}&sessionId=${this.data.sessionId}` }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '安全确认没有保存成功，请重试' }) } finally { this.setData({ loading: false }) } },
})
