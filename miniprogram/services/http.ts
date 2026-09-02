import type { ApiEnvelope, ApiError, EnvironmentKind } from '../types/api'
import { sessionStore } from '../stores/session'

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: Record<string, unknown>
  idempotencyKey?: string
}

const now = (): string => new Date().toISOString()
let demoCommunityConsent = false
let demoAccountStatus: 'active' | 'recovery' = 'active'

const getEnvironment = (): EnvironmentKind => {
  const app = getApp<{ globalData: { environmentKind?: EnvironmentKind } }>()
  return app.globalData.environmentKind ?? 'unconfigured'
}

export const newRequestId = (): string => `wx-${Date.now()}-${Math.random().toString(16).slice(2)}`

export const apiError = (code: ApiError['code'], message: string, retryable = false): ApiError => ({
  code,
  message,
  retryable,
})

const envelope = <T>(data: T | null, error: ApiError | null = null): ApiEnvelope<T> => ({
  request_id: newRequestId(),
  data,
  error,
})

const demoResponse = <T>(path: string, options: RequestOptions): ApiEnvelope<T> => {
  const method = options.method ?? 'GET'
  if (path === '/auth/wechat/session') {
    return envelope({
      access_token: '',
      access_expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
      identity_status: 'unverified',
      base_consent_status: 'pending',
      community_consent_status: 'withdrawn',
      account_status: 'active',
    } as T)
  }
  if (path === '/today') {
    return envelope({
      quote: { text: '慢一点，也是在向前走。', attribution: '——心语 V2', available: true },
      mood: null,
      recentObservation: null,
    } as T)
  }
  if (path === '/consents/base') return envelope({ ok: true } as T)
  if (path === '/consents/community' && method === 'POST') { demoCommunityConsent = options.data?.action === 'accepted'; return envelope({ displayName: '匿名同学', accountStatus: demoAccountStatus, recoveryUntil: null, basicConsent: true, communityConsent: demoCommunityConsent, identityVerified: true } as T) }
  if (path === '/identity/verifications' && method === 'POST') return envelope({ verification_id: 'demo-verification', status: 'verified' } as T)
  if (path === '/moods/today' && method === 'PUT') {
    return envelope({ record_id: 'demo-mood', mood_code: String(options.data?.mood_code ?? ''), saved_at: now() } as T)
  }
  if (path === '/assessment-modules') {
    return envelope([
      { key: 'phq9', title: '抑郁情绪自测', purpose: '观察最近两周的情绪体验', duration: '约 3 分钟', questionCount: 9, lastCompletedAt: null },
      { key: 'gad7', title: '焦虑自测', purpose: '观察最近两周的紧张与担忧', duration: '约 3 分钟', questionCount: 7, lastCompletedAt: null },
      { key: 'sleep', title: '睡眠观察', purpose: '记录入睡、夜间和白天感受', duration: '约 3 分钟', questionCount: 8, lastCompletedAt: null },
    ] as T)
  }
  if (path.includes('/support-resource-ack') && method === 'POST') return envelope({ ok: true } as T)
  if (path.includes('/safety-confirmation') && method === 'POST') return envelope({ next_step: 'continue_assessment', result_id: null, support_required: false, task_created: false } as T)
  if (path.includes('/complete') && method === 'POST') {
    const module = String(options.data?.module_code ?? 'phq9') as 'phq9' | 'gad7' | 'sleep'
    const answers = Array.isArray(options.data?.answers) ? options.data?.answers as number[] : []
    const safetyState = undefined
    if (module === 'sleep') return envelope({ id: 'demo-result', module, title: '睡眠观察', completedAt: now(), kind: 'ordinary', score: null, interpretation: '这次观察记录了入睡、夜间情况和白天感受。', nextStep: '可以在几天后再次观察，留意变化。', sleepDimensions: [{ name: '入睡', summary: '可以留意入睡所需时间' }, { name: '夜间情况', summary: '可以留意夜间醒来情况' }, { name: '白天感受', summary: '可以留意白天精力变化' }] } as T)
    const score = answers.reduce((sum, value) => sum + value, 0)
    return envelope({ id: 'demo-result', module, title: module === 'gad7' ? '焦虑自测' : '抑郁情绪自测', completedAt: now(), kind: score >= 10 ? 'higher_score' : 'ordinary', score, interpretation: score >= 10 ? '这次结果提示你可以多留意最近的感受，并考虑找可信任的人聊聊。' : '这次结果提供了一个当下的观察切面，可以结合自己的感受理解它。', nextStep: '如果这些感受持续影响生活，可以考虑联系校内支持。', safetyState } as T)
  }
  if (path === '/assessment-sessions' && method === 'POST') {
    const module = String(options.data?.module_code ?? 'phq9') as 'phq9' | 'gad7' | 'sleep'
    const count = module === 'phq9' ? 9 : module === 'gad7' ? 7 : 8
    const title = module === 'phq9' ? '抑郁情绪自测' : module === 'gad7' ? '焦虑自测' : '睡眠观察'
    const questions = Array.from({ length: count }, (_, index) => ({
      id: `${module}-${index + 1}`,
      prompt: module === 'sleep' ? `过去一周，你对睡眠观察维度 ${index + 1} 的感受是？` : `在过去两周，你有多常出现第 ${index + 1} 项描述的感受？`,
      options: ['完全没有', '有几天', '一半以上天数', '几乎每天'],
    }))
    return envelope({ session_id: `demo-${module}`, module_code: module, title, questionnaire_version: 'v1', questions } as T)
  }
  if (path === '/support-resources') {
    return envelope([
      { id: 'trusted', group: 'trusted_person', title: '现在可以联系谁', description: '如果你愿意，可以先联系一位信任的人，告诉对方你现在需要陪伴。', updatedAt: '演示配置' },
      { id: 'campus', group: 'campus', title: '校内心理支持', description: '请通过学校公开渠道联系心理中心，获取预约与陪伴支持。', updatedAt: '演示配置' },
      { id: 'emergency', group: 'emergency', title: '当地紧急支持', description: '如果你现在无法保证安全，请联系当地紧急服务或前往最近的急诊。', updatedAt: '演示配置' },
    ] as T)
  }
  if (path === '/treehole/posts' && method === 'GET') {
    return envelope([
      { id: 'post-1', displayName: '一片云', body: null, excerpt: '最近有点累，想找个地方把心事放下。', status: 'published', createdAt: now(), responseCount: 1, mine: false, responses: [] },
      { id: 'post-2', displayName: '晚风', body: null, excerpt: '今天完成了一件拖了很久的小事。', status: 'protected', createdAt: now(), responseCount: 0, mine: false, responses: [] },
    ] as T)
  }
  if (path.startsWith('/treehole/posts/') && path.endsWith('/responses') && method === 'POST') return envelope({ ok: true } as T)
  if (path.startsWith('/treehole/posts/') && method === 'GET') return envelope({ id: path.split('/')[3], displayName: '一片云', body: '最近有点累，想找个地方把心事放下。', excerpt: '最近有点累，想找个地方把心事放下。', status: 'published', createdAt: now(), responseCount: 1, mine: false, responses: [{ id: 'response-1', displayName: '晚风', body: '谢谢你愿意写下来，愿你今天有一点喘息的空间。', createdAt: now(), status: 'published' }] } as T)
  if (path === '/treehole/posts' && method === 'POST') return envelope({ id: 'demo-post', displayName: '一片云', body: null, excerpt: String(options.data?.body ?? '').slice(0, 80), status: 'checking', createdAt: now(), responseCount: 0, mine: true } as T)
  if (path === '/me') {
    return envelope({ ...sessionStore.getUser(), displayName: sessionStore.getUser().displayName ?? '匿名同学', accountStatus: demoAccountStatus, communityConsent: demoCommunityConsent, identityVerified: Boolean(sessionStore.getUser().identityVerified) } as T)
  }
  if (path === '/account/stop' && method === 'POST') { demoAccountStatus = 'recovery'; return envelope({ ok: true } as T) }
  if (path === '/account/recover' && method === 'POST') { demoAccountStatus = 'active'; return envelope({ ok: true } as T) }
  if (path === '/moods' && method === 'GET') return envelope([] as T)
  if (path === '/assessment-results' && method === 'GET') return envelope([] as T)
  if (path.startsWith('/moods/') && method === 'DELETE') return envelope({ ok: true } as T)
  if (path.startsWith('/assessment-results/') && method === 'DELETE') return envelope({ ok: true } as T)
  if (path === '/me/treehole/posts') return envelope([] as T)
  return envelope<T>(null, apiError('UNAVAILABLE', '当前环境尚未配置学生端服务，请稍后重试。', true))
}

export const request = <T>(path: string, options: RequestOptions = {}): Promise<ApiEnvelope<T>> => {
  const app = getApp<{ globalData: { apiBaseUrl?: string } }>()
  const baseUrl = app.globalData.apiBaseUrl ?? ''
  if (getEnvironment() === 'demo' && !baseUrl) {
    return Promise.resolve(demoResponse<T>(path, options))
  }
  if (!baseUrl) return Promise.resolve(envelope<T>(null, apiError('UNAVAILABLE', '当前环境尚未配置学生端服务，请稍后重试。', true)))
  return new Promise((resolve) => {
    wx.request<ApiEnvelope<T>>({
      url: `${baseUrl}${path}`,
      method: options.method ?? 'GET',
      data: options.data,
      timeout: 8000,
      header: {
        Authorization: sessionStore.accessToken() ? `Bearer ${sessionStore.accessToken()}` : '',
        'X-Request-ID': newRequestId(),
        ...(options.idempotencyKey ? { 'Idempotency-Key': options.idempotencyKey } : {}),
      },
      success: (response) => {
        const result = response.data ?? envelope<T>(null, apiError('UNAVAILABLE', '服务返回暂时不可用，请稍后重试。', true))
        if (result.error?.code === 'UNAUTHORIZED') sessionStore.clear()
        resolve(result)
      },
      fail: () => resolve(envelope<T>(null, apiError('NETWORK_ERROR', '网络暂时不可用，请稍后重试。', true))),
    })
  })
}
