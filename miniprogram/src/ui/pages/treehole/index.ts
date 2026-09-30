import { fetchPosts } from '../../../services/treehole'
import { displayTime } from '../../shared/scripts/display-time'
import type { TreeholePost } from '../../../infra/types/api'
import { sessionStore } from '../../../infra/store/session'

Page({
  data: { loading: true, error: '', posts: [] as Array<TreeholePost & { displayTime: string }> },
  onShow() { this.load() },
  async load() { this.setData({ loading: true, error: '' }); try { const posts = await fetchPosts(); this.setData({ posts: posts.map((post) => ({ ...post, displayTime: displayTime(post.createdAt) })) }) } catch { this.setData({ error: '暂时没有加载到内容' }) } finally { this.setData({ loading: false }) } },
  open(event: WechatMiniprogram.BaseEvent) { const id = (event.currentTarget as WechatMiniprogram.Target).dataset.id as string; wx.navigateTo({ url: `/ui/pages/treehole-detail/index?id=${id}` }) },
  publish() { const user = sessionStore.getUser(); if (!user.identityVerified) { wx.navigateTo({ url: '/ui/pages/identity-verification/index?from=treehole' }); return } if (!user.communityConsent) { wx.navigateTo({ url: '/ui/pages/privacy/index?focus=community' }); return } wx.navigateTo({ url: '/ui/pages/treehole-publish/index' }) },
})
