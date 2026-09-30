import assert from 'node:assert/strict'
import { test } from 'node:test'
import { MOOD_OPTIONS, moodLabel } from '../../src/services/mood.ts'

test('mood codes use the six confirmed Chinese labels', () => {
  assert.deepEqual(MOOD_OPTIONS, [
    { code: 'pleasant', label: '愉快' },
    { code: 'calm', label: '平静' },
    { code: 'tired', label: '疲惫' },
    { code: 'anxious', label: '焦虑' },
    { code: 'low', label: '低落' },
    { code: 'irritable', label: '烦躁' },
  ])
})

test('moodLabel translates API codes and preserves an unknown fallback', () => {
  assert.equal(moodLabel('pleasant'), '愉快')
  assert.equal(moodLabel('irritable'), '烦躁')
  assert.equal(moodLabel('自定义状态'), '自定义状态')
  assert.equal(moodLabel(null), '')
})
