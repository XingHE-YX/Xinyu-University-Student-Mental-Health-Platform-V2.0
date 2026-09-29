import { fetchModules, startAssessment } from '../../services/assessment'
import type { AssessmentModule } from '../../types/api'
import { sessionStore } from '../../stores/session'

Page({
  data: { loading: true, error: '', modules: [] as AssessmentModule[] },
  onShow() { this.load() },
  async load() { this.setData({ loading: true, error: '' }); try { this.setData({ modules: await fetchModules() }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '自测目录暂时不可用' }) } finally { this.setData({ loading: false }) } },
  async begin(event: WechatMiniprogram.BaseEvent) { const key = (event.currentTarget as WechatMiniprogram.Target).dataset.key as AssessmentModule['key']; const current = sessionStore.get(); if (!current?.identityVerified) { wx.navigateTo({ url: `/pages/identity-verification/index?from=assessment-${key}` }); return } if (current.accountStatus === 'recovery') { this.setData({ error: '账户处于恢复期，恢复后才能开始新的观察' }); return } try { const session = await startAssessment(key); wx.navigateTo({ url: `/pages/assessment-answer/index?sessionId=${session.id}&module=${session.module}&title=${encodeURIComponent(session.title)}&questions=${encodeURIComponent(JSON.stringify(session.questions))}` }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '暂时无法开始本次观察' }) } },
  history() { wx.navigateTo({ url: '/pages/history/index' }) },
})
