import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  normalizeAssessmentModules,
  normalizeHistoryItems,
  normalizeTodayShortcuts,
  normalizeTodayObservations,
  normalizeTreeholePost,
  normalizeTreeholePosts,
} from '../../src/services/normalizers.ts'

test('normalizes paginated assessment modules from the backend contract', () => {
  assert.deepEqual(normalizeAssessmentModules({ modules: [{ module_code: 'sleep_observation', title: '睡眠与作息自我观察', description: '观察睡眠', expected_minutes: 3, latest_completed_date: '2026-09-06' }] }), [
    { key: 'sleep', title: '睡眠与作息观察', purpose: '观察睡眠', duration: '约 3 分钟', questionCount: 0, lastCompletedAt: '2026-09-06' },
  ])
})

test('missing history and module containers are errors, not empty success states', () => {
  for (const run of [() => normalizeAssessmentModules({}), () => normalizeHistoryItems({ unexpected: [] })]) {
    assert.throws(run, (error) => error.code === 'INVALID_RESPONSE' && /暂时/.test(error.userMessage))
  }
})

test('today keeps three separate observations and preserves the support entry', () => {
  const observations = normalizeTodayObservations([
    { module_code: 'gad7', title: 'GAD-7', latest_completed_date: '2026-09-06' },
    { module_code: 'phq9', safety_entry_required: true, latest_completed_text: '2026-09-07' },
  ])
  assert.deepEqual(observations.map((item) => item.title), ['情绪状态', '焦虑状态', '睡眠与恢复'])
  assert.equal(observations[0].summary, '这次记录需要先单独查看')
  assert.equal(observations[0].safetyEntryRequired, true)
  assert.equal(observations[1].summary, '2026-09-06')
  assert.equal(observations[2].summary, '尚未记录')
})

test('nonpublic and protected posts do not leak excerpts or unpublished responses', () => {
  for (const status of ['unpublished', 'pending_confirmation', 'safety_priority', 'deleted']) {
    const post = normalizeTreeholePost({ status, body: 'private', excerpt: 'private', responses: [{ status: 'published', body: 'private' }] })
    assert.equal(post.body, null)
    assert.equal(post.excerpt, null)
    assert.deepEqual(post.responses, [])
  }
  const post = normalizeTreeholePost({ status: 'protected', body: 'allowed in detail', excerpt: 'must be collapsed', responses: [{ state: 'unpublished', body_sanitized: 'hidden' }] })
  assert.equal(post.excerpt, null)
  assert.deepEqual(post.responses, [])
})

test('normalizes treehole list and detail projections', () => {
  const post = normalizeTreeholePost({ post_id: 'post-1', display_name_snapshot: '一片云', body_sanitized: '最近有点累', visibility_state: 'published', created_at: '2026-09-07T12:00:00Z', response_count: 1, mine: false, responses: [] })
  assert.equal(post.id, 'post-1')
  assert.equal(post.displayName, '一片云')
  assert.equal(post.body, '最近有点累')
  assert.equal(post.excerpt, '最近有点累')
  assert.equal(post.status, 'published')
  assert.deepEqual(normalizeTreeholePosts({ items: [{ post_id: 'post-1', display_name_snapshot: '一片云', body_sanitized: null, visibility_state: 'protected', created_at: '2026-09-07T12:00:00Z', response_count: 0, mine: false }] }).map((item) => item.id), ['post-1'])
})

test('normalizes history pages and today assessment shortcuts', () => {
  assert.deepEqual(normalizeHistoryItems({ items: [{ record_id: 'mood-1', mood_code: 'calm', saved_at: '2026-09-07T12:00:00Z' }] }), [{ record_id: 'mood-1', mood_code: 'calm', saved_at: '2026-09-07T12:00:00Z' }])
  assert.deepEqual(normalizeTodayShortcuts([{ module_code: 'phq9', title: 'PHQ-9', latest_completed_text: '尚未记录', latest_completed_date: null, description: '情绪观察', safety_entry_required: false }]), [{ module_code: 'phq9', title: 'PHQ-9', latest_completed_text: '尚未记录', latest_completed_date: null, description: '情绪观察', safety_entry_required: false }])
})
