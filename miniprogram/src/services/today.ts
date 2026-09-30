import { assertApiData } from '../infra/error'
import { request } from '../infra/http'
import { formatMoodTime, moodDateKey, moodLabel } from './mood'
import { normalizeTodayObservations } from './normalizers'
import type { MoodRecord, TodayProjection } from '../infra/types/api'
import { createLogger } from '../infra/logger'

const log = createLogger('services.today')

export const fetchToday = async (): Promise<TodayProjection> => {
  const result = await request<Record<string, unknown>>('/today')
  assertApiData(result, '今日内容暂时不可用')
  const data = result.data
  const quote = (data.quote ?? {}) as Record<string, unknown>
  const mood = (data.mood_today ?? data.mood ?? null) as Record<string, unknown> | null
  const observations = normalizeTodayObservations(data.assessment_shortcuts)
  return { quote: { text: String(quote.quote_text ?? quote.text ?? ''), attribution: [quote.author_text, quote.work_text].filter(Boolean).join(' / ') || String(quote.attribution ?? ''), available: Boolean(quote.quote_text ?? quote.text) }, mood: mood ? { id: String(mood.record_id ?? mood.id ?? ''), mood: moodLabel(mood.mood_code ?? mood.mood), recordedAt: formatMoodTime(mood.saved_at ?? mood.recordedAt) } : null, recentObservation: observations[0]?.summary ?? (data.recent_observation ? String(data.recent_observation) : null), observations }
}

export const saveMood = async (mood: string): Promise<MoodRecord> => {
  const recordDate = moodDateKey()
  const result = await request<Record<string, unknown>>('/moods/today', { method: 'PUT', data: { record_date: recordDate, mood_code: mood, object_version: 1 }, idempotencyKey: `mood-${recordDate}` })
  assertApiData(result, '没有保存成功，请再试一次')
  const data = result.data
  log.audit('mood.saved', { outcome: 'success', requestId: result.request_id })
  return { id: String(data.record_id ?? data.id ?? ''), mood: moodLabel(data.mood_code ?? data.mood ?? mood), recordedAt: formatMoodTime(data.saved_at ?? data.recordedAt ?? new Date().toISOString()) }
}
