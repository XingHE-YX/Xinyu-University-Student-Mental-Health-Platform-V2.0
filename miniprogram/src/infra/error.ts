import type { ApiEnvelope, ApiError, ApiErrorCode } from './types/api'

export type ErrorCategory = 'configuration' | 'network' | 'http' | 'business' | 'validation' | 'state' | 'unknown'
export type AppErrorCode = ApiErrorCode | 'CONFIGURATION_ERROR' | 'TIMEOUT' | 'HTTP_ERROR'
  | 'INVALID_RESPONSE' | 'WX_API_ERROR' | 'STATE_ERROR' | 'UNKNOWN_ERROR'

interface ErrorDefinition {
  category: ErrorCategory
  message: string
  userMessage: string
  retryable: boolean
}

export const errorDefinitions: Readonly<Record<AppErrorCode, ErrorDefinition>> = {
  UNAUTHORIZED: { category: 'business', message: 'Session is unauthorized', userMessage: '登录状态已失效，请重新进入', retryable: false },
  CONSENT_REQUIRED: { category: 'business', message: 'Consent is required', userMessage: '请先确认相关服务说明', retryable: false },
  IDENTITY_REQUIRED: { category: 'business', message: 'Identity verification is required', userMessage: '请先完成身份核验', retryable: false },
  ACCOUNT_STOPPED: { category: 'business', message: 'Account is stopped', userMessage: '请先恢复账户再继续操作', retryable: false },
  CONFLICT: { category: 'business', message: 'Resource version conflicts', userMessage: '状态已发生变化，请刷新后重试', retryable: false },
  UNAVAILABLE: { category: 'business', message: 'Service is unavailable', userMessage: '服务暂时不可用，请稍后重试', retryable: true },
  VALIDATION_ERROR: { category: 'validation', message: 'Input validation failed', userMessage: '请检查输入内容后重试', retryable: false },
  NETWORK_ERROR: { category: 'network', message: 'Network request failed', userMessage: '网络暂时不可用，请稍后重试', retryable: true },
  NOT_FOUND: { category: 'business', message: 'Resource was not found', userMessage: '内容暂时无法查看，请刷新后重试', retryable: false },
  CONFIGURATION_ERROR: { category: 'configuration', message: 'Runtime configuration is missing', userMessage: '当前环境尚未配置学生端服务，请稍后重试', retryable: false },
  TIMEOUT: { category: 'network', message: 'Network request timed out', userMessage: '请求超时，请稍后重试', retryable: true },
  HTTP_ERROR: { category: 'http', message: 'HTTP request failed', userMessage: '服务暂时不可用，请稍后重试', retryable: false },
  INVALID_RESPONSE: { category: 'validation', message: 'Response does not match the API contract', userMessage: '内容暂时无法读取，请稍后重试', retryable: false },
  WX_API_ERROR: { category: 'state', message: 'WeChat API call failed', userMessage: '微信服务暂时不可用，请稍后重试', retryable: false },
  STATE_ERROR: { category: 'state', message: 'Local state does not allow this operation', userMessage: '当前状态已变化，请重新进入后重试', retryable: false },
  UNKNOWN_ERROR: { category: 'unknown', message: 'Unexpected application error', userMessage: '暂时无法完成操作，请稍后重试', retryable: false },
}

export interface ErrorContext {
  scope?: string
  operation?: string
}

export interface AppErrorOptions {
  message?: string
  userMessage?: string
  retryable?: boolean
  requestId?: string
  clientRequestId?: string
  statusCode?: number
  backendCode?: string
  cause?: unknown
  context?: ErrorContext
}

export class AppError extends Error {
  readonly code: AppErrorCode
  readonly category: ErrorCategory
  readonly userMessage: string
  readonly retryable: boolean
  readonly requestId?: string
  readonly clientRequestId?: string
  readonly statusCode?: number
  readonly backendCode?: string
  readonly cause?: unknown
  readonly context: Readonly<ErrorContext>

  constructor(code: AppErrorCode, options: AppErrorOptions = {}) {
    const definition = errorDefinitions[code]
    super(options.message ?? definition.message)
    this.name = 'AppError'
    this.code = code
    this.category = definition.category
    this.userMessage = options.userMessage ?? definition.userMessage
    this.retryable = options.retryable ?? definition.retryable
    this.requestId = options.requestId
    this.clientRequestId = options.clientRequestId
    this.statusCode = options.statusCode
    this.backendCode = options.backendCode
    this.cause = options.cause
    this.context = Object.freeze({ ...options.context })
  }
}

export const fromApiError = (error: ApiError, options: AppErrorOptions = {}): AppError => {
  const code = Object.prototype.hasOwnProperty.call(errorDefinitions, error.code) ? error.code : 'UNKNOWN_ERROR'
  return new AppError(code, {
    ...options,
    backendCode: error.code,
    cause: error,
    userMessage: code === 'UNKNOWN_ERROR' ? options.userMessage : error.message || options.userMessage,
    retryable: code === 'UNKNOWN_ERROR' ? false : error.retryable,
  })
}

export const normalizeError = (value: unknown, options: AppErrorOptions = {}): AppError => {
  if (value instanceof AppError) return value
  return new AppError('UNKNOWN_ERROR', {
    ...options,
    message: value instanceof Error ? value.message : typeof value === 'string' ? value : undefined,
    cause: value,
  })
}

export const getUserMessage = (value: unknown, fallback?: string): string =>
  normalizeError(value, { userMessage: fallback }).userMessage

export type ApiResult<T> = ApiEnvelope<T> & {
  clientError?: AppError
  clientRequestId?: string
  statusCode?: number
}

export function assertApiSuccess<T>(result: ApiResult<T>, fallback?: string): void {
  if (result.clientError) throw result.clientError
  if (result.error) throw fromApiError(result.error, {
    requestId: result.request_id,
    clientRequestId: result.clientRequestId,
    statusCode: result.statusCode,
    userMessage: fallback,
  })
}

export function assertApiData<T>(result: ApiResult<T>, fallback?: string): asserts result is ApiResult<T> & { data: T } {
  assertApiSuccess(result, fallback)
  if (result.data === null || result.data === undefined) throw new AppError('INVALID_RESPONSE', {
    requestId: result.request_id,
    clientRequestId: result.clientRequestId,
    statusCode: result.statusCode,
    userMessage: fallback,
  })
}
