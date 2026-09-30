import { handlePageError } from '../../shared/scripts/page-error'
import { fetchMyPosts } from '../../../services/treehole'
import type { TreeholePost } from '../../../infra/types/api'
Page({ data: { loading: true, error: '', posts: [] as TreeholePost[] }, onShow() { this.load() }, async load() { try { this.setData({ posts: await fetchMyPosts() }) } catch (error) { this.setData({ error: handlePageError(error, '我的内容暂时不可用') }) } finally { this.setData({ loading: false }) } }, open(event: WechatMiniprogram.BaseEvent) { const id = (event.currentTarget as WechatMiniprogram.Target).dataset.id as string; wx.navigateTo({ url: `/ui/pages/treehole-detail/index?id=${id}` }) }, publish() { wx.navigateTo({ url: '/ui/pages/treehole-publish/index' }) } })
