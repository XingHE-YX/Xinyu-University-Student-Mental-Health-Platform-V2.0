import { assertApiData, assertApiSuccess } from '../infra/error'
import { request } from '../infra/http'
import { normalizeTreeholePost, normalizeTreeholePosts } from './normalizers'
import type { TreeholePost } from '../infra/types/api'

export const fetchPosts = async (): Promise<TreeholePost[]> => {
  const result = await request<Record<string, unknown> | TreeholePost[]>('/treehole/posts', { data: { sort: 'latest', limit: 20 } })
  assertApiData(result, '树洞内容暂时不可用')
  return normalizeTreeholePosts(result.data)
}

export const fetchPost = async (id: string): Promise<TreeholePost> => {
  const result = await request<Record<string, unknown>>(`/treehole/posts/${id}`)
  assertApiData(result, '帖子暂时不可见')
  return normalizeTreeholePost(result.data)
}

export const publishPost = async (body: string): Promise<TreeholePost> => {
  const idempotencyKey = `post-${Date.now()}`
  const result = await request<Record<string, unknown>>('/treehole/posts', { method: 'POST', data: { body, client_idempotency_key: idempotencyKey }, idempotencyKey })
  assertApiData(result, '内容没有提交成功，请稍后重试')
  const data = result.data
  return normalizeTreeholePost(data.display_projection ?? data)
}

export const respondToPost = async (id: string, body: string): Promise<void> => {
  const idempotencyKey = `response-${id}-${Date.now()}`
  const result = await request(`/treehole/posts/${id}/responses`, { method: 'POST', data: { body, object_version: 1, client_idempotency_key: idempotencyKey }, idempotencyKey })
  assertApiSuccess(result)
}

export const deletePost = async (id: string): Promise<void> => {
  const result = await request(`/treehole/posts/${id}`, { method: 'DELETE', data: { object_version: 1 }, idempotencyKey: `delete-post-${id}` })
  assertApiSuccess(result)
}

export const fetchMyPosts = async (): Promise<TreeholePost[]> => {
  const result = await request<Record<string, unknown> | TreeholePost[]>('/me/treehole/posts')
  assertApiData(result, '我的内容暂时不可用')
  return normalizeTreeholePosts(result.data)
}
