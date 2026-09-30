import assert from 'node:assert/strict'
import { test } from 'node:test'
import { moodDateKey } from '../../src/infra/date.ts'
import { formatMoodTime } from '../../src/services/mood.ts'
import { displayTime } from '../../src/ui/shared/scripts/display-time.ts'

test('formatMoodTime keeps the page state compact and readable', () => {
  assert.equal(formatMoodTime('2026-09-07T14:32:11+08:00'), '14:32')
  assert.equal(formatMoodTime('not-a-date'), 'not-a-date')
})

test('moodDateKey follows the Shanghai calendar at midnight, independent of device timezone', () => {
  assert.equal(moodDateKey(new Date('2026-09-06T16:30:00Z')), '2026-09-07')
  assert.equal(moodDateKey(new Date('2026-09-06T15:59:00Z')), '2026-09-06')
})

test('relative display time handles minute, hour and calendar boundaries', () => {
  const now = new Date('2026-09-30T12:00:00+08:00')
  assert.equal(displayTime('2026-09-30T11:59:50+08:00', now), '刚刚')
  assert.equal(displayTime('2026-09-30T11:01:00+08:00', now), '59 分钟前')
  assert.equal(displayTime('2026-09-29T13:00:00+08:00', now), '23 小时前')
  assert.equal(displayTime('not-a-date', now), '')
})
