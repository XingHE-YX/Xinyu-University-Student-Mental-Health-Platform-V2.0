import { request } from './http'
import type { AssessmentAiAssist, AssessmentModule, AssessmentResult, AssessmentSession, SupportResource } from '../types/api'

export const fetchModules = async (): Promise<AssessmentModule[]> => {
  const result = await request<Array<Record<string, unknown>>>('/assessment-modules')
  if (result.error || !result.data) throw new Error(result.error?.message ?? '自测目录暂时不可用')
  return result.data.map((module) => ({ key: String(module.module_code ?? module.key) as AssessmentModule['key'], title: String(module.title ?? ''), purpose: String(module.description ?? module.purpose ?? ''), duration: `约 ${String(module.expected_minutes ?? 3)} 分钟`, questionCount: Number(module.question_count ?? module.questionCount ?? 0), lastCompletedAt: (module.last_completed_at ?? module.lastCompletedAt ?? null) as string | null }))
}

export const startAssessment = async (module: AssessmentModule['key']): Promise<AssessmentSession> => {
  const idempotencyKey = `assessment-start-${module}-${Date.now()}`
  const result = await request<Record<string, unknown>>('/assessment-sessions', { method: 'POST', data: { module_code: module, client_start_key: idempotencyKey }, idempotencyKey })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '暂时无法开始本次观察')
  const data = result.data
  const questions = Array.isArray(data.questions) ? data.questions as Array<Record<string, unknown>> : []
  return { id: String(data.session_id ?? data.id ?? ''), module: String(data.module_code ?? module) as AssessmentModule['key'], title: module === 'phq9' ? '抑郁情绪自测' : module === 'gad7' ? '焦虑自测' : '睡眠观察', questionnaireVersion: String(data.questionnaire_version ?? 'v1'), questions: questions.map((question, index) => ({ id: String(question.question_key ?? question.id ?? `${module}-${index + 1}`), prompt: String(question.prompt ?? question.text ?? `第 ${index + 1} 题`), options: Array.isArray(question.options) ? question.options.map(String) : ['完全没有', '有几天', '一半以上天数', '几乎每天'] })) }
}

export const submitAssessment = async (sessionId: string, module: AssessmentModule['key'], answers: number[], safetyState?: string): Promise<AssessmentResult> => {
  const result = await request<Record<string, unknown>>(`/assessment-sessions/${sessionId}/complete`, { method: 'POST', data: { module_code: module, answers: answers.map((option, index) => ({ question_key: `${module}-${index + 1}`, option_key: String(option) })), object_version: 1 }, idempotencyKey: `assessment-submit-${sessionId}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '结果暂时没有保存成功，请稍后重试')
  return normalizeAssessmentResult(result.data, module)
}

const normalizeAssessmentResult = (data: Record<string, unknown>, fallbackModule: AssessmentModule['key']): AssessmentResult => {
  const ai = normalizeAiAssist(data.ai_assist ?? data.aiAssist)
  return {
    id: String(data.result_id ?? data.id ?? ''),
    module: String(data.module_code ?? fallbackModule) as AssessmentModule['key'],
    title: String(data.title ?? (fallbackModule === 'phq9' ? '抑郁情绪自测' : fallbackModule === 'gad7' ? '焦虑自测' : '睡眠观察')),
    completedAt: String(data.completed_at ?? data.completedAt ?? ''),
    kind: String(data.result_state ?? data.kind ?? 'ordinary') as AssessmentResult['kind'],
    score: typeof data.score === 'number' ? data.score : null,
    interpretation: String(data.fixed_summary ?? data.interpretation ?? ''),
    nextStep: String(data.next_step ?? data.nextStep ?? '可以按自己的节奏决定是否查看支持资源。'),
    sleepDimensions: Array.isArray(data.dimension_summary) ? data.dimension_summary as AssessmentResult['sleepDimensions'] : undefined,
    safetyState: typeof data.safety_state === 'string' ? data.safety_state as AssessmentResult['safetyState'] : undefined,
    aiAssist: ai,
  }
}

const normalizeAiAssist = (value: unknown): AssessmentAiAssist | undefined => {
  if (!value || typeof value !== 'object') return undefined
  const data = value as Record<string, unknown>
  const output = data.output_projection ?? data.output ?? data
  if (!output || typeof output !== 'object') return undefined
  const projection = output as Record<string, unknown>
  const status = data.output_status === 'fallback' || data.status === 'fallback' ? 'fallback' : data.output_status === 'adopted' || data.status === 'adopted' || projection.status === 'ok' ? 'adopted' : undefined
  if (!status) return undefined
  return {
    status,
    summary: typeof projection.summary === 'string' ? projection.summary : undefined,
    observations: Array.isArray(projection.observations) ? projection.observations.filter((item): item is string => typeof item === 'string') : undefined,
    practicalSteps: Array.isArray(projection.practical_steps) ? projection.practical_steps.filter((item): item is string => typeof item === 'string') : undefined,
    boundaryNotice: typeof projection.boundary_notice === 'string' ? projection.boundary_notice : undefined,
    fallbackCopy: typeof data.fallback_copy === 'string' ? data.fallback_copy : undefined,
  }
}

export const confirmSafety = async (sessionId: string, state: 'can_be_safe' | 'uncertain' | 'cannot_be_safe', answers: number[] = []): Promise<void> => {
  const result = await request(`/assessment-sessions/${sessionId}/safety-confirmation`, { method: 'POST', data: { state, answers: answers.map((option, index) => ({ question_key: `phq9-${index + 1}`, option_key: String(option) })), object_version: 1 }, idempotencyKey: `safety-${sessionId}` })
  if (result.error) throw new Error(result.error.message)
}

export const acknowledgeSupportResources = async (sessionId: string): Promise<void> => {
  const result = await request(`/assessment-sessions/${sessionId}/support-resource-ack`, { method: 'POST', data: { resource_context: 'safety', resource_version: 'v1', object_version: 1 }, idempotencyKey: `support-ack-${sessionId}` })
  if (result.error) throw new Error(result.error.message)
}

export const fetchResources = async (context: 'ordinary' | 'safety' = 'ordinary'): Promise<SupportResource[]> => {
  const result = await request<SupportResource[]>('/support-resources', { data: { context: context === 'safety' ? 'safety' : 'normal' } })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '支持资源暂时不可用')
  return result.data
}
