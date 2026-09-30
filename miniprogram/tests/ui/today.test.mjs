import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { installWxMock } from '../helpers/wx-mock.mjs'

let pageDefinition
globalThis.Page = (page) => { pageDefinition = page }
await import('../../src/ui/pages/today/index.ts')
const makeTodayPage = () => {
  const page = { ...pageDefinition, data: structuredClone(pageDefinition.data) }
  page.setData = (value) => Object.assign(page.data, value)
  return page
}
let fixture
let responses
let requests
beforeEach(() => {
  fixture = installWxMock()
  responses = fixture.responses
  requests = fixture.requests
})

test('mood failures stay in the sheet; retry succeeds without losing the selection', async () => {
  const page = makeTodayPage()
  page.data.loaded = true
  page.data.loading = false
  page.openMoodSheet()
  assert.equal(fixture.tabBarVisible, false)
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
  assert.equal(fixture.tabBarVisible, true)
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

test('today navigation uses the registered UI routes', () => {
  const page = makeTodayPage()
  page.goAssessment()
  page.goTreehole()
  page.goSupport()
  page.goMy()
  assert.deepEqual(fixture.navigations.map(({ method, url }) => ({ method, url })), [
    { method: 'switchTab', url: '/ui/pages/assessment-center/index' },
    { method: 'switchTab', url: '/ui/pages/treehole/index' },
    { method: 'navigateTo', url: '/ui/pages/support-resources/index' },
    { method: 'switchTab', url: '/ui/pages/my/index' },
  ])
})
