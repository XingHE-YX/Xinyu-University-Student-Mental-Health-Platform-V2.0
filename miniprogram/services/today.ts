import { request } from './http'
import type { MoodRecord, TodayProjection } from '../types/api'

export const fetchToday = async (): Promise<TodayProjection> => {
  const result = await request<Record<string, unknown>>('/today')
  if (result.error || !result.data) throw new Error(result.error?.message ?? '今日内容暂时不可用')
  const data = result.data
  const quote = (data.quote ?? {}) as Record<string, unknown>
  const mood = (data.mood_today ?? data.mood ?? null) as Record<string, unknown> | null
  return { quote: { text: String(quote.quote_text ?? quote.text ?? ''), attribution: [quote.author_text, quote.work_text].filter(Boolean).join(' / ') || String(quote.attribution ?? ''), available: Boolean(quote.quote_text ?? quote.text) }, mood: mood ? { id: String(mood.record_id ?? mood.id ?? ''), mood: String(mood.mood_code ?? mood.mood ?? ''), recordedAt: String(mood.saved_at ?? mood.recordedAt ?? '') } : null, recentObservation: data.recent_observation ? String(data.recent_observation) : null }
}

export const saveMood = async (mood: string): Promise<MoodRecord> => {
  const result = await request<Record<string, unknown>>('/moods/today', { method: 'PUT', data: { record_date: new Date().toISOString().slice(0, 10), mood_code: mood, object_version: 0 }, idempotencyKey: `mood-${new Date().toISOString().slice(0, 10)}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '没有保存成功，请再试一次')
  const data = result.data
  return { id: String(data.record_id ?? data.id ?? ''), mood: String(data.mood_code ?? data.mood ?? mood), recordedAt: String(data.saved_at ?? data.recordedAt ?? new Date().toISOString()) }
}
