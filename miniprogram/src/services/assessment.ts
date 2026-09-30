import { request } from '../infra/http'
import { normalizeAssessmentModules } from './normalizers'
import type { AssessmentAiAssist, AssessmentModule, AssessmentResult, AssessmentSession, SupportResource } from '../infra/types/api'

const activeSessions = new Map<string, { questions: AssessmentSession['questions']; version: number }>()
let supportResourceVersion = ''

const sessionContext = (id: string) => {
  const context = activeSessions.get(id)
  if (!context) throw new Error('本次观察会话已失效，请重新开始')
  return context
}

const answerPayload = (sessionId: string, answers: number[]) => {
  const { questions } = sessionContext(sessionId)
  return answers.map((option, index) => {
    const question = questions[index]
    if (!question || !question.optionKeys?.[option]) throw new Error('请重新选择当前答案')
    return { question_key: question.id, option_key: question.optionKeys[option] }
  })
}

const apiModuleCode = (module: AssessmentModule['key']): 'phq9' | 'gad7' | 'sleep_observation' => module === 'sleep' ? 'sleep_observation' : module

const displayModuleTitle = (module: AssessmentModule['key']): string => module === 'phq9' ? '抑郁情绪自测' : module === 'gad7' ? '焦虑自测' : '睡眠观察'

export const fetchModules = async (): Promise<AssessmentModule[]> => {
  const result = await request<Record<string, unknown> | Array<Record<string, unknown>>>('/assessment-modules')
  if (result.error || !result.data) throw new Error(result.error?.message ?? '自测目录暂时不可用')
  return normalizeAssessmentModules(result.data)
}

export const startAssessment = async (module: AssessmentModule['key']): Promise<AssessmentSession> => {
  const idempotencyKey = `assessment-start-${module}-${Date.now()}`
  const result = await request<Record<string, unknown>>('/assessment-sessions', { method: 'POST', data: { module_code: apiModuleCode(module), client_start_key: idempotencyKey }, idempotencyKey })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '暂时无法开始本次观察')
  const data = result.data
  const questions = Array.isArray(data.questions) ? data.questions as Array<Record<string, unknown>> : []
  const session: AssessmentSession = {
    id: String(data.session_id ?? data.id ?? ''), module,
    title: String(data.title ?? displayModuleTitle(module)),
    questionnaireVersion: String(data.questionnaire_version ?? 'v1'),
    questions: questions.map((question, index) => {
      const options = Array.isArray(question.options) ? question.options : []
      return {
        id: String(question.question_key ?? question.id ?? `${module}-q${index + 1}`),
        prompt: String(question.prompt ?? question.text ?? `第 ${index + 1} 题`),
        options: options.map((option) => option && typeof option === 'object' ? String((option as Record<string, unknown>).label ?? '') : String(option)),
        optionKeys: options.map((option, optionIndex) => option && typeof option === 'object' ? String((option as Record<string, unknown>).option_key) : String(optionIndex)),
      }
    }),
  }
  activeSessions.set(session.id, { questions: session.questions, version: Number(data.object_version ?? 1) })
  return session
}

export const submitAssessment = async (sessionId: string, module: AssessmentModule['key'], answers: number[], _safetyState?: string): Promise<AssessmentResult> => {
  const context = sessionContext(sessionId)
  const result = await request<Record<string, unknown>>(`/assessment-sessions/${sessionId}/complete`, { method: 'POST', data: { answers: answerPayload(sessionId, answers), object_version: context.version }, idempotencyKey: `assessment-submit-${sessionId}-${context.version}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '结果暂时没有保存成功，请稍后重试')
  if (result.data.completion_state !== 'result_ready' || !result.data.result_id) throw new Error('请先完成安全确认并查看支持资源')
  return fetchAssessmentResult(String(result.data.result_id), module)
}

export const fetchAssessmentResult = async (id: string, module: AssessmentModule['key'] = 'phq9'): Promise<AssessmentResult> => {
  const result = await request<Record<string, unknown>>(`/assessment-results/${id}`)
  if (result.error || !result.data) throw new Error(result.error?.message ?? '本次记录暂时无法展示')
  return normalizeAssessmentResult(result.data, module)
}

export const abandonAssessment = async (sessionId: string): Promise<void> => {
  const context = sessionContext(sessionId)
  const result = await request(`/assessment-sessions/${sessionId}/abandon`, { method: 'POST', data: { object_version: context.version }, idempotencyKey: `abandon-${sessionId}` })
  if (result.error) throw new Error(result.error.message)
  activeSessions.delete(sessionId)
}

const normalizeAssessmentResult = (data: Record<string, unknown>, fallbackModule: AssessmentModule['key']): AssessmentResult => {
  const ai = normalizeAiAssist(data.ai_assist ?? data.aiAssist)
  const module = data.module_code === 'sleep_observation' ? 'sleep' : String(data.module_code ?? fallbackModule) as AssessmentModule['key']
  const dimensions = data.dimension_summary as Record<string, unknown> | undefined
  return {
    id: String(data.result_id ?? data.id ?? ''),
    module,
    title: String(data.title ?? displayModuleTitle(module)),
    completedAt: String(data.created_at ?? data.completed_at ?? data.completedAt ?? '').replace('T', ' ').slice(0, 16),
    kind: String(data.result_state ?? data.kind ?? 'ordinary') as AssessmentResult['kind'],
    score: typeof data.score === 'number' ? data.score : null,
    interpretation: String(data.fixed_summary ?? data.interpretation ?? ''),
    nextStep: String(data.next_step ?? data.nextStep ?? '可以按自己的节奏决定是否查看支持资源。'),
    sleepDimensions: module === 'sleep' && dimensions ? [{ name: '作息节律', summary: String(dimensions.rhythm ?? '') }, { name: '睡前阻力', summary: String(dimensions.bedtime_resistance ?? '') }, { name: '恢复与日间影响', summary: String(dimensions.recovery_daytime_impact ?? '') }] : undefined,
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
  const context = sessionContext(sessionId)
  const result = await request<Record<string, unknown>>(`/assessment-sessions/${sessionId}/safety-confirmation`, { method: 'POST', data: { state, answers: answerPayload(sessionId, answers), object_version: context.version }, idempotencyKey: `safety-${sessionId}-${context.version}-${state}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '安全确认暂时不可用')
  context.version = Number(result.data.version)
}

export const acknowledgeSupportResources = async (sessionId: string): Promise<void> => {
  const context = sessionContext(sessionId)
  if (!supportResourceVersion) throw new Error('支持资源暂未配置，请稍后重试')
  const result = await request<Record<string, unknown>>(`/assessment-sessions/${sessionId}/support-resource-ack`, { method: 'POST', data: { resource_context: 'safety', resource_version: supportResourceVersion, object_version: context.version }, idempotencyKey: `support-ack-${sessionId}-${context.version}` })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '资源确认暂时不可用')
  context.version = Number(result.data.version)
}

export const fetchResources = async (context: 'ordinary' | 'safety' = 'ordinary'): Promise<SupportResource[]> => {
  const result = await request<Record<string, unknown> | SupportResource[]>('/support-resources', { data: { context: context === 'safety' ? 'safety' : 'normal' } })
  if (result.error || !result.data) throw new Error(result.error?.message ?? '支持资源暂时不可用')
  if (Array.isArray(result.data)) return result.data
  supportResourceVersion = String(result.data.resource_version ?? '')
  const resources = Array.isArray(result.data.resources) ? result.data.resources as Record<string, unknown>[] : []
  return resources.map((item) => ({
    id: String(item.resource_id), group: item.category as SupportResource['group'],
    title: String(item.title), description: String(item.description),
    phone: item.action_type === 'call' ? String(item.action_target) : undefined,
    url: item.action_type === 'open_url' ? String(item.action_target) : undefined,
    availabilityText: item.availability_text ? String(item.availability_text) : undefined,
    sourceText: item.source_text ? String(item.source_text) : undefined,
    updatedAt: String(item.verified_at ?? '').slice(0, 10),
  }))
}
