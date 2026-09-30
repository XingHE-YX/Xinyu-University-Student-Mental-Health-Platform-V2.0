import { normalizeError } from './error'
import type { AppErrorCode, ErrorCategory } from './error'
import type { EnvironmentKind } from './types/api'

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'
export interface LogContext {
  operation?: string
  route?: string
  method?: string
  outcome?: 'success' | 'failure'
  environment?: EnvironmentKind
  requestId?: string
  clientRequestId?: string
  durationMs?: number
  statusCode?: number
  code?: AppErrorCode
  category?: ErrorCategory
  retryable?: boolean
}

export interface LogEntry {
  timestamp: string
  level: LogLevel
  kind: 'diagnostic' | 'audit'
  scope: string
  event: string
  context: Readonly<LogContext>
  error?: { name: string; code: AppErrorCode; category: ErrorCategory; retryable: boolean; stack?: string }
}

export interface LoggerOptions {
  level?: LogLevel
  sink?: (entry: LogEntry) => void
  now?: () => Date
}

const levels: Record<LogLevel, number> = { debug: 0, info: 1, warn: 2, error: 3 }
const consoleSink = (entry: LogEntry): void => console[entry.level]('[xinyu]', entry)
let defaults: Required<LoggerOptions> = { level: 'warn', sink: consoleSink, now: () => new Date() }
const reportedErrors = new WeakSet<object>()
const identifier = (value: unknown): value is string =>
  typeof value === 'string' && value.length <= 128 && /^[a-zA-Z0-9_.:-]+$/.test(value)

export const configureLogger = (options: LoggerOptions): void => {
  defaults = { ...defaults, ...options }
}

const sanitizeContext = (context: LogContext): LogContext => {
  const output: LogContext = {}
  for (const key of ['operation', 'requestId', 'clientRequestId', 'code', 'category'] as const) {
    if (identifier(context[key])) Object.assign(output, { [key]: context[key] })
  }
  if (typeof context.route === 'string' && context.route.length <= 200 && /^\/(?:[a-z-]+|:id)(?:\/(?:[a-z-]+|:id))*$/.test(context.route)) output.route = context.route
  if (context.method && ['GET', 'POST', 'PUT', 'DELETE'].includes(context.method)) output.method = context.method
  if (context.outcome === 'success' || context.outcome === 'failure') output.outcome = context.outcome
  if (context.environment && ['demo', 'authorized', 'unconfigured'].includes(context.environment)) output.environment = context.environment
  for (const key of ['durationMs', 'statusCode'] as const) {
    if (typeof context[key] === 'number' && Number.isFinite(context[key])) output[key] = context[key]
  }
  if (typeof context.retryable === 'boolean') output.retryable = context.retryable
  return Object.freeze(output)
}

export const createLogger = (scope: string, options: LoggerOptions = {}) => {
  const write = (level: LogLevel, kind: LogEntry['kind'], event: string, context: LogContext = {}, value?: unknown): boolean => {
    const settings = { ...defaults, ...options }
    if (levels[level] < levels[settings.level]) return false
    const entry: LogEntry = {
      timestamp: settings.now().toISOString(), level, kind,
      scope: identifier(scope) ? scope : 'unknown',
      event: identifier(event) ? event : 'unknown',
      context: sanitizeContext(context),
    }
    if (value !== undefined) {
      const error = normalizeError(value)
      // Exclude the first stack line, which can contain user data in the message.
      const stack = (value instanceof Error ? value.stack : error.stack)?.split('\n')
        .filter((line) => /^\s+at /.test(line)).join('\n').slice(0, 2000)
      entry.error = { name: 'AppError', code: error.code, category: error.category, retryable: error.retryable, stack }
    }
    try { settings.sink(Object.freeze(entry)); return true } catch { return false }
  }
  return {
    debug: (event: string, context?: LogContext) => write('debug', 'diagnostic', event, context),
    info: (event: string, context?: LogContext) => write('info', 'diagnostic', event, context),
    warn: (event: string, context?: LogContext) => write('warn', 'diagnostic', event, context),
    error: (event: string, error?: unknown, context?: LogContext) => write('error', 'diagnostic', event, context, error),
    audit: (event: string, context?: LogContext) => write('info', 'audit', event, context),
  }
}

export const logErrorOnce = (scope: string, event: string, value: unknown, context: LogContext = {}): void => {
  const error = normalizeError(value)
  const key = value !== null && typeof value === 'object' ? value : error
  if (reportedErrors.has(key)) return
  if (createLogger(scope).error(event, value ?? error, {
    ...error.context, ...context, code: error.code, category: error.category, retryable: error.retryable,
    requestId: error.requestId ?? context.requestId,
    clientRequestId: error.clientRequestId ?? context.clientRequestId,
    statusCode: error.statusCode ?? context.statusCode,
  })) reportedErrors.add(key)
}
