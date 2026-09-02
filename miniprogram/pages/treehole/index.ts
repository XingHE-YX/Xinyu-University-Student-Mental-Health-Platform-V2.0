import { fetchPosts } from '../../services/treehole'
import type { TreeholePost } from '../../types/api'
import { sessionStore } from '../../stores/session'

Page({
  data: { loading: true, error: '', posts: [] as TreeholePost[] },
  onShow() { this.load() },
  async load() { this.setData({ loading: true, error: '' }); try { this.setData({ posts: await fetchPosts() }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '树洞内容暂时不可用' }) } finally { this.setData({ loading: false }) } },
  open(event: WechatMiniprogram.BaseEvent) { const id = (event.currentTarget as WechatMiniprogram.Target).dataset.id as string; wx.navigateTo({ url: `/pages/treehole-detail/index?id=${id}` }) },
  publish() { const user = sessionStore.getUser(); if (!user.identityVerified) { wx.navigateTo({ url: '/pages/identity-verification/index?from=treehole' }); return } if (!user.communityConsent) { wx.navigateTo({ url: '/pages/privacy/index?focus=community' }); return } wx.navigateTo({ url: '/pages/treehole-publish/index' }) },
})
