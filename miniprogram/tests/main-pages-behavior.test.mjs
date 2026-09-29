import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { fetchModules, fetchResources } from '../services/assessment.ts'
import { fetchPosts } from '../services/treehole.ts'
import { fetchToday, saveMood } from '../services/today.ts'
import { fetchHistory } from '../services/me.ts'
import { logoutSession } from '../services/auth.ts'
import { sessionStore } from '../stores/session.ts'

let pageDefinition
globalThis.Page = (page) => { pageDefinition = page }
await import('../pages/today/index.ts')
const makeTodayPage = () => {
  const page = { ...pageDefinition, data: structuredClone(pageDefinition.data) }
  page.setData = (value) => Object.assign(page.data, value)
  return page
}

let responses
let requests
let tabBarVisible
beforeEach(() => {
  responses = {}
  requests = []
  tabBarVisible = true
  sessionStore.clear()
  globalThis.getApp = () => ({ globalData: { apiBaseUrl: 'https://example.test/api/v1', environmentKind: 'authorized' } })
  globalThis.wx = {
    hideTabBar() { tabBarVisible = false },
    showTabBar() { tabBarVisible = true },
    request(options) {
      const path = options.url.replace('https://example.test/api/v1', '')
      requests.push({ path, method: options.method, data: options.data })
      const response = responses[path]
      if (!response) { options.fail(); return }
      options.success({ data: { request_id: 'fixture', data: response, error: null } })
    },
  }
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

test('mood failures stay in the sheet; retry succeeds without losing the selection', async () => {
  const page = makeTodayPage()
  page.data.loaded = true
  page.data.loading = false
  page.openMoodSheet()
  assert.equal(tabBarVisible, false)
  page.selectMood({ currentTarget: { dataset: { mood: 'tired' } } })
  await page.saveMood()
  assert.equal(page.data.moodError, '暂时没有记下这次选择')
  assert.equal(page.data.selectedMood, 'tired')
  assert.equal(page.data.mood, null)
  assert.equal(page.data.error, '')
  responses['/moods/today'] = { record_id: 'mood-1', mood_code: 'tired', saved_at: '2026-09-07T06:32:00Z' }
  await page.saveMood()
  assert.equal(page.data.mood.mood, '疲惫')
  assert.equal(page.data.showMoodSheet, true)
  page.closeMoodSheet()
  assert.equal(tabBarVisible, true)
  assert.equal(page.data.showMoodSheet, false)
})

test('closing the mood sheet without saving makes no request; saving prevents repeat taps', async () => {
  const page = makeTodayPage()
  page.data.loaded = true
  page.data.loading = false
  page.openMoodSheet()
  page.closeMoodSheet()
  assert.equal(requests.length, 0)
  page.data.saving = true
  page.data.selectedMood = 'calm'
  await page.saveMood()
  page.selectMood({ currentTarget: { dataset: { mood: 'low' } } })
  assert.equal(requests.length, 0)
  assert.equal(page.data.selectedMood, 'calm')
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
