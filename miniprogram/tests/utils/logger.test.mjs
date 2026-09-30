import assert from 'node:assert/strict'
import { test } from 'node:test'
import { AppError } from '../../src/infra/error.ts'
import { configureLogger, createLogger, logErrorOnce } from '../../src/infra/logger.ts'

test('logger filters levels and emits stable structured development audit events', () => {
  const entries = []
  const log = createLogger('services.auth', { level: 'info', sink: (entry) => entries.push(entry), now: () => new Date('2026-09-30T00:00:00Z') })
  log.debug('hidden')
  log.audit('session.login', { outcome: 'success', requestId: 'request-1' })
  log.warn('session.expired')
  assert.equal(entries.length, 2)
  assert.equal(entries[0].timestamp, '2026-09-30T00:00:00.000Z')
  assert.equal(entries[0].kind, 'audit')
  assert.equal(entries[0].scope, 'services.auth')
  assert.equal(entries[0].context.outcome, 'success')
  assert.ok(Object.isFrozen(entries[0].context))
})

test('logger retains only allowlisted metadata and excludes error messages and causes', () => {
  const entries = []
  const log = createLogger('http', { level: 'debug', sink: (entry) => entries.push(entry) })
  const privateData = 'private-student-data'
  const error = new AppError('NETWORK_ERROR', { message: privateData, cause: { token: privateData }, context: { body: privateData } })
  log.error('request.failed', error, {
    method: 'POST', route: '/treehole/posts/:id', durationMs: 20, statusCode: 503,
    body: privateData, token: privateData, name: privateData, studentNumber: privateData,
  })
  assert.doesNotMatch(JSON.stringify(entries), new RegExp(privateData))
  assert.equal(entries[0].error.code, 'NETWORK_ERROR')
  assert.equal(entries[0].context.method, 'POST')
  assert.equal(entries[0].context.durationMs, 20)
  assert.ok(entries[0].error.stack)
})

test('logger drops invalid identifiers, URLs and nonfinite numbers', () => {
  const entries = []
  createLogger('bad scope', { sink: (entry) => entries.push(entry) }).warn('bad event', {
    requestId: 'private data', route: '/posts/id?token=secret', durationMs: NaN, statusCode: Infinity,
  })
  assert.equal(entries[0].scope, 'unknown')
  assert.equal(entries[0].event, 'unknown')
  assert.deepEqual(entries[0].context, {})
})

test('logger output failures do not interrupt application flow', () => {
  const log = createLogger('app', { sink: () => { throw new Error('console unavailable') } })
  assert.doesNotThrow(() => log.error('app.error', new Error('failed')))
})

test('the same captured exception is recorded once across request and page handling', () => {
  const entries = []
  configureLogger({ level: 'debug', sink: (entry) => entries.push(entry) })
  const error = new AppError('TIMEOUT', { requestId: 'request-1' })
  logErrorOnce('http', 'request.failed', error)
  logErrorOnce('ui', 'page.failed', error)
  assert.equal(entries.length, 1)
  assert.equal(entries[0].context.requestId, 'request-1')
})
