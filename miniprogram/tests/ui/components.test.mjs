import assert from 'node:assert/strict'
import { test } from 'node:test'

test('primary button keeps loading and disabled behavior with its local inline layout state', async () => {
  let component
  globalThis.Component = (definition) => { component = definition }
  await import('../../src/ui/components/primary-button/index.ts')
  assert.equal(component.properties.inline.value, false)
  const events = []
  const instance = { data: { disabled: true, loading: false }, triggerEvent: (event) => events.push(event) }
  component.methods.onTap.call(instance)
  instance.data = { disabled: false, loading: true }
  component.methods.onTap.call(instance)
  assert.equal(events.length, 0)
  instance.data = { disabled: false, loading: false }
  component.methods.onTap.call(instance)
  assert.deepEqual(events, ['action'])
})
