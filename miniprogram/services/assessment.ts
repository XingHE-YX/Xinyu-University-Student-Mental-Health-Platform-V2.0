import { request } from './http'
import type { AssessmentModule, AssessmentResult, AssessmentSession, SupportResource } from '../types/api'

export const fetchModules = async (): Promise<AssessmentModule[]> => {
  const result = await request<Array<Record<string, unknown>>>('/assessment-modules')
  if (result.error || !result.data) throw new Error(result.error?.message ?? '自测目录暂时不可用')
  return result.data.map((module) => ({ key: String(module.module_code ?? module.key) as AssessmentModule['key'], title: String(module.title ?? ''), purpose: String(module.description ?? module.purpose ?? ''), duration: `约 ${String(module.expected_minutes ?? 3)} 分钟`, questionCount: Number(module.question_count ?? module.questionCount ?? 0), lastCompletedAt: (module.last_completed_at ?? module.lastCompletedAt ?? null) as string | null }))
}

export const startAssessment = async (module: AssessmentModule['key']): Promise<AssessmentSession> => {
  const result = await request<Record<string, unknown>>('/assessment-sessions', { method: 'POST', data: { module_code: module, client_start_key: `assessment-start-${module}-${Date.now()}` }, idempotencyKey: `assessment-start-${module}-${Date.now()}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '暂时无法开始本次观察')
  const data = result.data
  const questions = Array.isArray(data.questions) ? data.questions as Array<Record<string, unknown>> : []
  return { id: String(data.session_id ?? data.id ?? ''), module: String(data.module_code ?? module) as AssessmentModule['key'], title: module === 'phq9' ? '抑郁情绪自测' : module === 'gad7' ? '焦虑自测' : '睡眠观察', questionnaireVersion: String(data.questionnaire_version ?? 'v1'), questions: questions.map((question, index) => ({ id: String(question.question_key ?? question.id ?? `${module}-${index + 1}`), prompt: String(question.prompt ?? question.text ?? `第 ${index + 1} 题`), options: Array.isArray(question.options) ? question.options.map(String) : ['完全没有', '有几天', '一半以上天数', '几乎每天'] })) }
}

export const submitAssessment = async (sessionId: string, module: AssessmentModule['key'], answers: number[], safetyState?: string): Promise<AssessmentResult> => {
  const result = await request<AssessmentResult>(`/assessment-sessions/${sessionId}/complete`, { method: 'POST', data: { module_code: module, answers: answers.map((option, index) => ({ question_key: `${module}-${index + 1}`, option_key: String(option) })), object_version: 0 }, idempotencyKey: `assessment-submit-${sessionId}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '结果暂时没有保存成功，请稍后重试')
  return result.data
}

export const confirmSafety = async (sessionId: string, state: 'can_be_safe' | 'uncertain' | 'cannot_be_safe', answers: number[] = []): Promise<void> => {
  const result = await request(`/assessment-sessions/${sessionId}/safety-confirmation`, { method: 'POST', data: { state, answers: answers.map((option, index) => ({ question_key: `phq9-${index + 1}`, option_key: String(option) })), object_version: 0 }, idempotencyKey: `safety-${sessionId}` })
  if (result.error) throw new Error(result.error.message)
}

export const acknowledgeSupportResources = async (sessionId: string): Promise<void> => {
  const result = await request(`/assessment-sessions/${sessionId}/support-resource-ack`, { method: 'POST', data: { resource_context: 'safety', resource_version: 'v1', object_version: 0 }, idempotencyKey: `support-ack-${sessionId}` })
  if (result.error) throw new Error(result.error.message)
}

export const fetchResources = async (context: 'ordinary' | 'safety' = 'ordinary'): Promise<SupportResource[]> => {
  const result = await request<SupportResource[]>('/support-resources', { data: { context: context === 'safety' ? 'safety' : 'normal' } })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '支持资源暂时不可用')
  return result.data
}
