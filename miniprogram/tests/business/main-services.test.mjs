import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { installWxMock } from '../helpers/wx-mock.mjs'
import { fetchModules, fetchResources } from '../../src/services/assessment.ts'
import { fetchPosts } from '../../src/services/treehole.ts'
import { fetchToday, saveMood } from '../../src/services/today.ts'
import { fetchHistory } from '../../src/services/me.ts'
import { logoutSession } from '../../src/services/auth.ts'
import { sessionStore } from '../../src/infra/store/session.ts'
import { configureLogger } from '../../src/infra/logger.ts'

let responses
let requests
beforeEach(() => {
  const fixture = installWxMock()
  responses = fixture.responses
  requests = fixture.requests
})

test('successful business operations emit audit metadata without observation content', async () => {
  const entries = []
  configureLogger({ level: 'debug', sink: (entry) => entries.push(entry) })
  responses['/moods/today'] = { record_id: 'private-record', mood_code: 'tired', saved_at: '2026-09-07T06:32:00Z' }
  await saveMood('tired')
  const audits = entries.filter((entry) => entry.kind === 'audit')
  assert.equal(audits.length, 1)
  assert.equal(audits[0].event, 'mood.saved')
  assert.equal(audits[0].context.requestId, 'fixture')
  assert.doesNotMatch(JSON.stringify(entries), /private-record|tired|疲惫/)
})

test('main page services unwrap real backend responses into readable page data', async () => {
  responses['/assessment-modules'] = { modules: [{ module_code: 'sleep_observation', description: '记录最近七天', expected_minutes: 3, enabled: true, latest_completed_date: '2026-09-06' }] }
  responses['/treehole/posts'] = { items: [{ post_id: 'post-1', display_name_snapshot: '一片云', body_sanitized: '今天完成了一件小事。', visibility_state: 'published', created_at: '2026-09-07T06:32:00Z' }] }
  responses['/today'] = { quote: { quote_text: '慢一点。', author_text: '测试出处' }, mood_today: { record_id: 'mood-1', mood_code: 'calm', saved_at: '2026-09-07T06:32:00Z' }, assessment_shortcuts: [{ module_code: 'gad7', latest_completed_date: '2026-09-06' }] }
  const [modules, posts, today] = await Promise.all([fetchModules(), fetchPosts(), fetchToday()])
  assert.equal(modules[0].key, 'sleep')
  assert.equal(modules[0].lastCompletedAt, '2026-09-06')
  assert.equal(posts[0].displayName, '一片云')
  assert.equal(posts[0].excerpt, '今天完成了一件小事。')
  assert.equal(today.mood.mood, '平静')
  assert.equal(today.mood.recordedAt, '14:32')
  assert.equal(today.observations[1].summary, '2026-09-06')
})

test('support resources expose honest demo availability and source labels', async () => {
  responses['/support-resources'] = {
    resource_version: 'support-v1',
    resources: [{
      resource_id: 'support-demo-001',
      category: 'campus',
      title: '校内心理支持（演示占位）',
      description: '用于展示功能流程。',
      action_type: 'text_only',
      action_target: null,
      availability_text: '待学校授权，暂无真实联系方式',
      source_text: '心语 V2 答辩演示占位',
      verified_at: '2026-09-22T00:00:00Z',
    }],
  }

  const resources = await fetchResources()

  assert.equal(resources[0].availabilityText, '待学校授权，暂无真实联系方式')
  assert.equal(resources[0].sourceText, '心语 V2 答辩演示占位')
  assert.equal(resources[0].phone, undefined)
  assert.equal(resources[0].url, undefined)
})

test('saving a mood sends its code and displays the returned Chinese label', async () => {
  responses['/moods/today'] = { record_id: 'mood-1', mood_code: 'tired', saved_at: '2026-09-07T06:32:00Z' }
  const saved = await saveMood('tired')
  assert.equal(requests[0].data.mood_code, 'tired')
  assert.equal(saved.mood, '疲惫')
  assert.equal(saved.recordedAt, '14:32')
})

test('history accepts backend pages without losing the mood date or sort order', async () => {
  responses['/moods'] = { items: [{ record_id: 'mood-1', mood_code: 'calm', saved_at: '2026-09-07T06:32:00Z' }] }
  responses['/assessment-results'] = { items: [{ result_id: 'result-1', module_code: 'sleep_observation', created_at: '2026-09-08T06:32:00Z', fixed_summary: '睡眠观察' }] }
  const history = await fetchHistory()
  assert.deepEqual(history.map((item) => item.id), ['result-1', 'mood-1'])
  assert.equal(history[0].category, 'sleep')
  assert.equal(history[1].summary, '平静')
  assert.equal(history[1].recordedAt, '2026-09-07T06:32:00Z')
})

test('logout clears the local session even when the server cannot be reached', async () => {
  sessionStore.set({ accessToken: 'student-token', expiresAt: '2026-09-21T16:00:00Z', identityVerified: false, basicConsent: true, communityConsent: false, accountStatus: 'active' })

  await logoutSession()

  assert.equal(sessionStore.get(), null)
  assert.equal(requests[0].path, '/auth/logout')
})
