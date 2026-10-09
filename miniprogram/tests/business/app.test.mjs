import assert from 'node:assert/strict'
import { test } from 'node:test'
import { configureLogger } from '../../src/infra/logger.ts'

test('app initializes development logging and captures global failures without network requests', async () => {
  const entries = []
  let app
  let registrations = 0
  configureLogger({ sink: (entry) => entries.push(entry) })
  globalThis.wx = {
    getExtConfigSync: () => ({ apiBaseUrl: 'https://example.test/api/v2', environmentKind: 'demo' }),
    getAccountInfoSync: () => ({ miniProgram: { appId: 'unknown', envVersion: 'develop' } }),
    getDeviceInfo: () => ({ platform: 'devtools' }),
    request: () => assert.fail('startup must not request the backend'),
  }
  globalThis.App = (definition) => { app = definition; registrations += 1 }
  await import('../../src/app.ts')
  assert.equal(registrations, 1)
  app.onLaunch()
  const error = new Error('private failure detail')
  app.onError(error)
  app.onUnhandledRejection({ reason: error })
  assert.equal(entries.length, 2)
  assert.equal(entries[0].event, 'app.launch')
  assert.equal(entries[0].context.environment, 'demo')
  assert.equal(entries[1].event, 'app.error')
  assert.doesNotMatch(JSON.stringify(entries), /private failure detail/)
})
