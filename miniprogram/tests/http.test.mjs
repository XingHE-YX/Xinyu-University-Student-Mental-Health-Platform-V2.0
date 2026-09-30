import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { request } from '../src/infra/http.ts'
import { assertApiData } from '../src/infra/error.ts'
import { sessionStore } from '../src/infra/store/session.ts'

let definition
beforeEach(() => {
  sessionStore.clear()
  globalThis.getApp = () => ({ globalData: { apiBaseUrl: 'https://example.test/api/v1', environmentKind: 'authorized' } })
  globalThis.wx = { request(options) { definition = options } }
})

test('request IDs match the sent header and preserve distinct server IDs', async () => {
  const pending = request('/today')
  definition.success({ statusCode: 200, data: { request_id: 'server-id', data: {}, error: null } })
  const result = await pending
  assert.equal(result.clientRequestId, definition.header['X-Request-ID'])
  assert.equal(result.request_id, 'server-id')
  assert.equal(result.statusCode, 200)
})

test('transport failures distinguish timeout, network and synchronous WeChat errors', async () => {
  for (const [errMsg, code] of [['request:fail timeout', 'TIMEOUT'], ['request:fail', 'NETWORK_ERROR']]) {
    const pending = request('/today')
    const cause = { errMsg }
    definition.fail(cause)
    const result = await pending
    assert.equal(result.clientError.code, code)
    assert.equal(result.clientError.cause, cause)
    assert.equal(result.request_id, definition.header['X-Request-ID'])
    assert.throws(() => assertApiData(result), { code })
  }
  const cause = new Error('wx unavailable')
  globalThis.wx.request = () => { throw cause }
  assert.equal((await request('/today')).clientError.code, 'WX_API_ERROR')
})

test('missing configuration produces a configuration error without a request', async () => {
  globalThis.getApp = () => ({ globalData: {} })
  globalThis.wx.request = () => assert.fail('network must not be called')
  assert.equal((await request('/today')).clientError.code, 'CONFIGURATION_ERROR')
})

test('HTTP failures and invalid response envelopes remain distinct', async () => {
  for (const [statusCode, data, code] of [[503, 'unavailable', 'HTTP_ERROR'], [200, {}, 'INVALID_RESPONSE'], [200, { request_id: 'bad', data: {}, error: { code: 1 } }, 'INVALID_RESPONSE']]) {
    const pending = request('/today')
    definition.success({ statusCode, data })
    const result = await pending
    assert.equal(result.clientError.code, code)
    assert.equal(result.clientError.statusCode, statusCode)
    assert.equal(result.clientError.retryable, statusCode === 503)
  }
})

test('backend errors keep business codes, status and clear unauthorized sessions', async () => {
  sessionStore.set({ accessToken: 'test-token' })
  const pending = request('/today')
  definition.success({ statusCode: 401, data: { request_id: 'server-id', data: null, error: { code: 'UNAUTHORIZED', message: '请重新进入' } } })
  const result = await pending
  assert.equal(result.clientError.code, 'UNAUTHORIZED')
  assert.equal(result.clientError.statusCode, 401)
  assert.equal(result.clientError.requestId, 'server-id')
  assert.equal(sessionStore.get(), null)
})
