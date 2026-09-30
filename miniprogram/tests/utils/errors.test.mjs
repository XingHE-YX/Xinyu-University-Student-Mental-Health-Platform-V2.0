import assert from 'node:assert/strict'
import { test } from 'node:test'
import { AppError, errorDefinitions, fromApiError, normalizeError, getUserMessage, assertApiData, assertApiSuccess } from '../../src/infra/error.ts'

test('AppError preserves standard Error information and typed diagnostic metadata', () => {
  const cause = new Error('transport details')
  const error = new AppError('TIMEOUT', {
    requestId: 'server-request', clientRequestId: 'client-request', statusCode: 408,
    cause, context: { scope: 'http', operation: 'load' },
  })
  assert.ok(error instanceof Error)
  assert.equal(error.name, 'AppError')
  assert.equal(error.category, 'network')
  assert.equal(error.retryable, true)
  assert.equal(error.requestId, 'server-request')
  assert.equal(error.clientRequestId, 'client-request')
  assert.equal(error.statusCode, 408)
  assert.equal(error.cause, cause)
  assert.ok(error.stack)
  assert.ok(Object.isFrozen(error.context))
})

test('every defined error has an explicit category, message, user message and retry policy', () => {
  for (const definition of Object.values(errorDefinitions)) {
    assert.ok(definition.category)
    assert.ok(definition.message)
    assert.ok(definition.userMessage)
    assert.equal(typeof definition.retryable, 'boolean')
  }
})

test('API errors retain their original code and request correlation', () => {
  const error = fromApiError({ code: 'CONFLICT', message: '请重新加载', retryable: true }, { requestId: 'request' })
  assert.equal(error.code, 'CONFLICT')
  assert.equal(error.backendCode, 'CONFLICT')
  assert.equal(error.requestId, 'request')
  assert.equal(error.retryable, true)
  assert.equal(getUserMessage(error), '请重新加载')
})

test('unknown backend codes and arbitrary throws have a safe user message', () => {
  for (const code of ['NEW_SERVER_CODE', '__proto__']) {
    const error = fromApiError({ code, message: 'internal server detail', retryable: true })
    assert.equal(error.code, 'UNKNOWN_ERROR')
    assert.equal(error.backendCode, code)
    assert.equal(error.retryable, false)
    assert.doesNotMatch(error.userMessage, /internal/)
  }
  for (const value of [new Error('private detail'), 'private detail', null, undefined, { detail: 'private' }]) {
    const error = normalizeError(value, { userMessage: '暂时无法加载' })
    assert.equal(error.cause, value)
    assert.equal(getUserMessage(value, '暂时无法加载'), '暂时无法加载')
  }
})

test('API assertions preserve client errors and distinguish missing data from empty results', () => {
  const error = new AppError('NETWORK_ERROR')
  assert.throws(() => assertApiSuccess({ clientError: error }), (actual) => actual === error)
  assert.throws(() => assertApiData({ request_id: 'empty', data: null, error: null }), { code: 'INVALID_RESPONSE', requestId: 'empty' })
  for (const data of [false, 0, '', [], {}]) assert.doesNotThrow(() => assertApiData({ request_id: 'ok', data, error: null }))
  assert.doesNotThrow(() => assertApiSuccess({ request_id: 'ok', data: null, error: null }))
})
