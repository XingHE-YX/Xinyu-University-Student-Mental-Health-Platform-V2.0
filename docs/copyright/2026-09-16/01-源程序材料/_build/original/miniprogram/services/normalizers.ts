import { moodLabel } from './mood'
import type { AssessmentModule, HistoryItem, TodayObservation, TreeholePost, TreeholeResponse } from '../types/api'

type UnknownRecord = Record<string, unknown>

const record = (value: unknown): UnknownRecord => value && typeof value === 'object' ? value as UnknownRecord : {}
const listFrom = (value: unknown, key: string): UnknownRecord[] => {
  if (Array.isArray(value)) return value.filter((item): item is UnknownRecord => Boolean(item && typeof item === 'object'))
  const wrapped = record(value)[key]
  if (!Array.isArray(wrapped)) throw new Error('内容暂时无法读取，请重新试试。')
  return wrapped.filter((item): item is UnknownRecord => Boolean(item && typeof item === 'object'))
}

export const normalizeAssessmentModules = (value: unknown): AssessmentModule[] => listFrom(value, 'modules')
  .filter((item) => item.enabled !== false)
  .map((item) => {
    const code = String(item.module_code ?? item.key)
    if (!['phq9', 'gad7', 'sleep', 'sleep_observation'].includes(code)) throw new Error('自测目录暂时无法读取。')
    const key = (code === 'sleep_observation' ? 'sleep' : code) as AssessmentModule['key']
    return {
      key,
      title: key === 'phq9' ? '近两周情绪状态' : key === 'gad7' ? '近两周焦虑状态' : '睡眠与作息观察',
      purpose: String(item.description ?? item.purpose ?? ''),
      duration: String(item.duration ?? `约 ${Number(item.expected_minutes ?? 3)} 分钟`),
      questionCount: Number(item.question_count ?? item.questionCount ?? 0),
      lastCompletedAt: (item.latest_completed_date ?? item.last_completed_at ?? item.lastCompletedAt ?? null) as string | null,
    }
  })

export const normalizeTreeholePost = (value: unknown): TreeholePost => {
  const item = record(value)
  const status = String(item.visibility_state ?? item.status ?? 'unpublished') as TreeholePost['status']
  const visible = status === 'published' || status === 'protected'
  const body = visible ? ('body_sanitized' in item ? item.body_sanitized : item.body) ?? null : null
  const excerpt = status === 'published' ? item.excerpt ?? body : null
  const responses = visible && Array.isArray(item.responses) ? item.responses.filter((response) => {
    const data = record(response)
    return (data.state ?? data.status) === 'published'
  }).map(normalizeTreeholeResponse) : []
  return {
    id: String(item.post_id ?? item.id ?? ''),
    displayName: String(item.display_name_snapshot ?? item.displayName ?? '匿名同学'),
    body: body == null ? null : String(body),
    excerpt: excerpt == null ? null : String(excerpt),
    status,
    createdAt: String(item.created_at ?? item.createdAt ?? ''),
    responseCount: Number(item.response_count ?? item.responseCount ?? responses.length),
    responses,
    mine: Boolean(item.mine),
  }
}

const normalizeTreeholeResponse = (value: unknown): TreeholeResponse => {
  const item = record(value)
  return {
    id: String(item.response_id ?? item.id ?? ''),
    displayName: String(item.display_name_snapshot ?? item.displayName ?? '匿名同学'),
    body: String(item.body_sanitized ?? item.body ?? ''),
    createdAt: String(item.created_at ?? item.createdAt ?? ''),
    status: String(item.state ?? item.status ?? 'published') === 'checking' ? 'checking' : 'published',
  }
}

export const normalizeTreeholePosts = (value: unknown): TreeholePost[] => listFrom(value, 'items').map(normalizeTreeholePost)

export const normalizeHistoryItems = (value: unknown): UnknownRecord[] => listFrom(value, 'items')

export const normalizeTodayShortcuts = (value: unknown): UnknownRecord[] => Array.isArray(value) ? value.map(record) : []

export const normalizeTodayObservations = (value: unknown): TodayObservation[] => {
  const items = normalizeTodayShortcuts(value)
  return (['phq9', 'gad7', 'sleep'] as const).map((key) => {
    const item = items.find((item) => (item.module_code ?? item.key) === key || (key === 'sleep' && item.module_code === 'sleep_observation'))
    const safetyEntryRequired = Boolean(item?.safety_entry_required)
    return {
      key,
      title: key === 'phq9' ? '情绪状态' : key === 'gad7' ? '焦虑状态' : '睡眠与恢复',
      summary: safetyEntryRequired ? '这次记录需要先单独查看' : String(item?.latest_completed_date ?? item?.latest_completed_text ?? '尚未记录'),
      safetyEntryRequired,
    }
  })
}

export const normalizeMoodHistoryItem = (value: unknown): HistoryItem => {
  const item = record(value)
  return { id: String(item.record_id ?? item.id ?? ''), category: 'mood', title: '今日心情', summary: moodLabel(item.mood_code ?? item.mood), recordedAt: String(item.saved_at ?? item.created_at ?? item.recordedAt ?? ''), deletable: true }
}
