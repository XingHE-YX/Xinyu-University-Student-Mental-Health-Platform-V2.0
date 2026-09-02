import { request } from './http'
import type { HistoryItem, UserProjection } from '../types/api'
import { fetchUser } from './auth'

export const fetchHistory = async (category?: HistoryItem['category']): Promise<HistoryItem[]> => {
  const [moods, results] = await Promise.all([request<Array<Record<string, unknown>>>('/moods', { data: { limit: 20 } }), request<Array<Record<string, unknown>>>('/assessment-results', { data: { limit: 20 } })])
  if (moods.error || results.error || !moods.data || !results.data) throw new Error(moods.error?.message ?? results.error?.message ?? '历史记录暂时不可用')
  const moodItems: HistoryItem[] = category && category !== 'mood' ? [] : moods.data.map((item) => ({ id: String(item.record_id ?? item.id ?? ''), category: 'mood', title: '今日心情', summary: String(item.mood_code ?? item.mood ?? ''), recordedAt: String(item.created_at ?? item.recordedAt ?? ''), deletable: true }))
  const resultItems: HistoryItem[] = category === 'mood' ? [] : results.data.map((item) => ({ id: String(item.result_id ?? item.id ?? ''), category: item.module_code === 'sleep' ? 'sleep' : 'assessment', title: String(item.title ?? item.module_code ?? '自测记录'), summary: String(item.fixed_summary ?? item.summary ?? '观察结果'), recordedAt: String(item.completed_at ?? item.recordedAt ?? ''), deletable: true }))
  return [...moodItems, ...resultItems]
}

export const deleteHistoryItem = async (id: string, category: HistoryItem['category'] = 'assessment'): Promise<void> => {
  const endpoint = category === 'mood' ? `/moods/${id}` : `/assessment-results/${id}`
  const result = await request(endpoint, { method: 'DELETE', data: { object_version: 1 }, idempotencyKey: `delete-history-${id}` })
  if (result.error) throw new Error(result.error.message)
}

export const fetchProfile = async (): Promise<UserProjection> => {
  return fetchUser()
}
