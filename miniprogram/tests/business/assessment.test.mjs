import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { installWxMock } from '../helpers/wx-mock.mjs'
import { startAssessment, confirmSafety, fetchResources, acknowledgeSupportResources } from '../../src/services/assessment.ts'

let fixture
beforeEach(() => { fixture = installWxMock() })

test('assessment safety and resource acknowledgement retain answer keys and object versions', async () => {
  fixture.responses['/assessment-sessions'] = {
    session_id: 'fixture-session', object_version: 1,
    questions: [{ question_key: 'q1', prompt: 'fixture question', options: [{ option_key: 'never', label: '完全没有' }] }],
  }
  fixture.responses['/assessment-sessions/fixture-session/safety-confirmation'] = { version: 2 }
  fixture.responses['/support-resources'] = { resource_version: 'fixture-resources', resources: [] }
  fixture.responses['/assessment-sessions/fixture-session/support-resource-ack'] = { version: 3 }
  const session = await startAssessment('phq9')
  await confirmSafety(session.id, 'uncertain', [0])
  await fetchResources('safety')
  await acknowledgeSupportResources(session.id)
  assert.deepEqual(fixture.requests[1].data.answers, [{ question_key: 'q1', option_key: 'never' }])
  assert.equal(fixture.requests[1].data.object_version, 1)
  assert.equal(fixture.requests[3].data.object_version, 2)
  assert.equal(fixture.requests[3].data.resource_version, 'fixture-resources')
})

test('missing assessment state raises a typed state error before issuing a request', async () => {
  await assert.rejects(confirmSafety('missing-session', 'uncertain', []), { code: 'STATE_ERROR', category: 'state' })
  assert.equal(fixture.requests.length, 0)
})
