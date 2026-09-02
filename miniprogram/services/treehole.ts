import { request } from './http'
import type { TreeholePost } from '../types/api'

export const fetchPosts = async (): Promise<TreeholePost[]> => {
  const result = await request<TreeholePost[]>('/treehole/posts', { data: { sort: 'latest', limit: 20 } })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '树洞内容暂时不可用')
  return result.data
}

export const fetchPost = async (id: string): Promise<TreeholePost> => {
  const result = await request<TreeholePost>(`/treehole/posts/${id}`)
  if (result.error || !result.data) throw new Error(result.error?.message ?? '帖子暂时不可见')
  return result.data
}

export const publishPost = async (body: string): Promise<TreeholePost> => {
  const result = await request<TreeholePost>('/treehole/posts', { method: 'POST', data: { body, client_idempotency_key: `post-${Date.now()}` }, idempotencyKey: `post-${Date.now()}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '内容没有提交成功，请稍后重试')
  return result.data
}

export const respondToPost = async (id: string, body: string): Promise<void> => {
  const result = await request(`/treehole/posts/${id}/responses`, { method: 'POST', data: { body, object_version: 0, client_idempotency_key: `response-${id}-${Date.now()}` }, idempotencyKey: `response-${id}-${Date.now()}` })
  if (result.error) throw new Error(result.error.message)
}

export const deletePost = async (id: string): Promise<void> => {
  const result = await request(`/treehole/posts/${id}`, { method: 'DELETE', data: { object_version: 0 }, idempotencyKey: `delete-post-${id}` })
  if (result.error) throw new Error(result.error.message)
}

export const fetchMyPosts = async (): Promise<TreeholePost[]> => {
  const result = await request<TreeholePost[]>('/me/treehole/posts')
  if (result.error || !result.data) throw new Error(result.error?.message ?? '我的内容暂时不可用')
  return result.data
}
