import { publishPost } from '../../services/treehole'

Page({
  data: { body: '', loading: false, error: '', checked: false },
  onInput(event: WechatMiniprogram.TextareaInput) { this.setData({ body: event.detail.value, error: '', checked: false }) },
  check() { if (!this.data.body.trim()) { this.setData({ error: '请先写下一段内容' }); return } if (this.data.body.length > 1000) { this.setData({ error: '内容最多 1000 字，请适当精简' }); return } this.setData({ checked: true, error: '' }) },
  async submit() { if (!this.data.checked) { this.check(); if (!this.data.checked) return } this.setData({ loading: true, error: '' }); try { const post = await publishPost(this.data.body.trim()); wx.redirectTo({ url: `/pages/treehole-status/index?id=${post.id}&status=${post.status}` }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '内容没有提交成功，请稍后重试' }) } finally { this.setData({ loading: false }) } },
})
