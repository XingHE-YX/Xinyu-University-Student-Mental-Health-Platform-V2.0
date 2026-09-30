export const MOOD_OPTIONS = [
  { code: 'pleasant', label: '愉快' },
  { code: 'calm', label: '平静' },
  { code: 'tired', label: '疲惫' },
  { code: 'anxious', label: '焦虑' },
  { code: 'low', label: '低落' },
  { code: 'irritable', label: '烦躁' },
] as const

const MOOD_LABELS: Record<string, string> = Object.fromEntries(MOOD_OPTIONS.map((item) => [item.code, item.label]))

export const moodLabel = (value: unknown): string => {
  const code = String(value ?? '')
  return MOOD_LABELS[code] ?? code
}

export const formatMoodTime = (value: unknown): string => {
  const raw = String(value ?? '')
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  const shanghai = new Date(date.getTime() + 8 * 60 * 60 * 1000)
  return `${String(shanghai.getUTCHours()).padStart(2, '0')}:${String(shanghai.getUTCMinutes()).padStart(2, '0')}`
}

export { moodDateKey } from '../infra/date'
