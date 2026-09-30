import { fetchToday, saveMood } from '../../../services/today'
import { MOOD_OPTIONS, moodDateKey } from '../../../services/mood'
import { sessionStore } from '../../../infra/store/session'
import type { MoodRecord, QuoteProjection, TodayObservation } from '../../../infra/types/api'

Page({
  data: { loading: true, loaded: false, recordDate: '', saving: false, error: '', moodError: '', quote: null as QuoteProjection | null, mood: null as MoodRecord | null, observations: [] as TodayObservation[], selectedMood: '', showMoodSheet: false, todayDate: '', greeting: '', moods: [...MOOD_OPTIONS] },
  onShow() { this.setDateContext(); if (this.data.showMoodSheet) wx.hideTabBar({ animation: false }); if (!this.data.saving) this.load() },
  onHide() { wx.showTabBar({ animation: false }) },
  onUnload() { wx.showTabBar({ animation: false }) },
  setDateContext() { const now = new Date(); const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']; const hour = now.getHours(); this.setData({ todayDate: `${now.getMonth() + 1}月${now.getDate()}日 ${weekdays[now.getDay()]}`, greeting: hour < 6 ? '夜深了，先照顾好自己。' : hour < 12 ? '早上好，按自己的节奏开始今天。' : hour < 18 ? '下午好，留一点时间给自己。' : '晚上好，今天也辛苦了。' }) },
  async load() {
    const recordDate = moodDateKey()
    if (this.data.recordDate !== recordDate) this.setData({ loaded: false, mood: null, observations: [], selectedMood: '', moodError: '', recordDate })
    this.setData({ loading: true, error: '' })
    try {
      const today = await fetchToday()
      this.setData({ quote: today.quote, mood: today.mood, observations: today.observations, loaded: true })
    } catch { this.setData({ error: '暂时无法读取今天的内容，请重新试试。' }) }
    finally { this.setData({ loading: false }) }
  },
  selectMood(event: WechatMiniprogram.BaseEvent) {
    if (this.data.mood || this.data.saving) return
    const code = (event.currentTarget as WechatMiniprogram.Target).dataset.mood as string
    if (MOOD_OPTIONS.some((item) => item.code === code)) this.setData({ selectedMood: code, moodError: '' })
  },
  async saveMood() {
    if (this.data.saving || this.data.mood) return
    if (!this.data.selectedMood) { this.setData({ moodError: '请先选择今天的心情' }); return }
    if (sessionStore.get()?.accountStatus === 'recovery') { this.setData({ moodError: '账户处于恢复期，恢复后才能记录' }); return }
    this.setData({ saving: true, moodError: '' })
    try { const mood = await saveMood(this.data.selectedMood); this.setData({ mood, selectedMood: '', moodError: '', loaded: true }) }
    catch { this.setData({ moodError: '暂时没有记下这次选择' }) }
    finally { this.setData({ saving: false }) }
  },
  openObservation(event: WechatMiniprogram.BaseEvent) {
    const key = (event.currentTarget as WechatMiniprogram.Target).dataset.key
    const observation = this.data.observations.find((item) => item.key === key)
    if (observation?.safetyEntryRequired) { wx.navigateTo({ url: '/ui/pages/support-resources/index?context=safety' }); return }
    this.goAssessment()
  },
  preventScroll() {},
  goAssessment() { wx.switchTab({ url: '/ui/pages/assessment-center/index' }) },
  openMoodSheet() { if (!this.data.loaded || this.data.loading) return; wx.hideTabBar({ animation: false }); this.setData({ showMoodSheet: true, moodError: '' }) },
  closeMoodSheet() { if (!this.data.saving) { wx.showTabBar({ animation: false }); this.setData({ showMoodSheet: false, selectedMood: '', moodError: '' }) } },
  goTreehole() { wx.switchTab({ url: '/ui/pages/treehole/index' }) },
  goSupport() { wx.navigateTo({ url: '/ui/pages/support-resources/index' }) },
  goMy() { wx.switchTab({ url: '/ui/pages/my/index' }) },
})
