import { fetchPost, respondToPost } from '../../services/treehole'
import type { TreeholePost } from '../../types/api'
import { sessionStore } from '../../stores/session'

Page({
  data: { loading: true, error: '', post: null as TreeholePost | null, id: '', response: '', responding: false },
  onLoad(query: Record<string, string>) { this.setData({ id: query.id ?? '' }); this.load() },
  async load() { try { this.setData({ loading: true, error: '' }); this.setData({ post: await fetchPost(this.data.id) }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '帖子暂时不可见' }) } finally { this.setData({ loading: false }) } },
  input(event: WechatMiniprogram.TextareaInput) { this.setData({ response: event.detail.value }) },
  async submitResponse() { if (!this.data.response.trim() || !this.data.post) return; const user = sessionStore.getUser(); if (!user.communityConsent) { this.setData({ error: '社区同意已撤回，暂时不能回应' }); return } this.setData({ responding: true, error: '' }); try { await respondToPost(this.data.post.id, this.data.response.trim()); this.setData({ response: '' }); await this.load() } catch (error) { this.setData({ error: error instanceof Error ? error.message : '回应没有提交成功，请稍后重试' }) } finally { this.setData({ responding: false }) } },
  manage() { wx.navigateTo({ url: `/pages/treehole-status/index?id=${this.data.id}&status=${this.data.post?.status ?? ''}&mine=true` }) },
})
