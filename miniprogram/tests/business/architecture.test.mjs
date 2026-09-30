import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import { test } from 'node:test'

const src = new URL('../../src/', import.meta.url)
const walk = async (url) => (await Promise.all((await readdir(url, { withFileTypes: true })).map(
  (entry) => entry.isDirectory() ? walk(new URL(`${entry.name}/`, url)) : new URL(entry.name, url),
))).flat()

test('infrastructure does not import services or UI modules', async () => {
  for (const file of await walk(new URL('infra/', src))) {
    if (!file.pathname.endsWith('.ts')) continue
    const source = await readFile(file, 'utf8')
    assert.doesNotMatch(source, /from ['"][^'"]*(?:services|ui)\//, file.pathname)
  }
})

test('business services do not depend on UI helpers', async () => {
  for (const file of await walk(new URL('services/', src))) {
    if (!file.pathname.endsWith('.ts')) continue
    assert.doesNotMatch(await readFile(file, 'utf8'), /from ['"][^'"]*ui\//, file.pathname)
  }
})
