import { fetchToday, saveMood } from '../../services/today'
import { sessionStore } from '../../stores/session'
import type { MoodRecord, QuoteProjection } from '../../types/api'

Page({
  data: { loading: true, saving: false, error: '', quote: null as QuoteProjection | null, mood: null as MoodRecord | null, selectedMood: '', recentObservation: '', moods: ['平静', '有点累', '低落', '焦虑', '还不错'] },
  onShow() { this.load() },
  async load() { this.setData({ loading: true, error: '' }); try { const today = await fetchToday(); this.setData({ quote: today.quote, mood: today.mood, recentObservation: today.recentObservation ?? '' }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '今日内容暂时不可用' }) } finally { this.setData({ loading: false }) } },
  selectMood(event: WechatMiniprogram.BaseEvent) { if (this.data.mood) return; this.setData({ selectedMood: (event.currentTarget as WechatMiniprogram.Target).dataset.mood as string, error: '' }) },
  async saveMood() { if (!this.data.selectedMood) { this.setData({ error: '请先选择今天的心情' }); return } if (sessionStore.get()?.accountStatus === 'recovery') { this.setData({ error: '账户处于恢复期，恢复后才能记录' }); return } this.setData({ saving: true, error: '' }); try { const mood = await saveMood(this.data.selectedMood); this.setData({ mood, selectedMood: '' }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '没有保存成功，请再试一次' }) } finally { this.setData({ saving: false }) } },
  goAssessment() { wx.switchTab({ url: '/pages/assessment-center/index' }) },
  goSupport() { wx.navigateTo({ url: '/pages/support-resources/index' }) },
  goMy() { wx.switchTab({ url: '/pages/my/index' }) },
})
