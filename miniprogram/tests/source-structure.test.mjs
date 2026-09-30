import assert from 'node:assert/strict'
import { access, readFile, readdir } from 'node:fs/promises'
import { test } from 'node:test'

const root = new URL('../', import.meta.url)
const src = new URL('src/', root)
const readJson = async (url) => JSON.parse(await readFile(url, 'utf8'))
const walk = async (url) => (await Promise.all((await readdir(url, { withFileTypes: true })).map(
  (entry) => entry.isDirectory() ? walk(new URL(`${entry.name}/`, url)) : new URL(entry.name, url),
))).flat()

test('WeChat loads src/app.ts and every declared page, component and tab icon exists', async () => {
  const config = await readJson(new URL('project.config.json', root))
  assert.equal(config.miniprogramRoot, 'src/')
  await access(new URL('app.ts', src))
  const app = await readJson(new URL('app.json', src))
  assert.equal(app.pages.length, 20)
  for (const page of app.pages) {
    assert.match(page, /^ui\/pages\//)
    for (const extension of ['ts', 'json', 'wxml']) await access(new URL(`${page}.${extension}`, src))
  }
  for (const tab of app.tabBar.list) {
    assert.ok(app.pages.includes(tab.pagePath))
    await access(new URL(tab.iconPath, src))
    await access(new URL(tab.selectedIconPath, src))
  }
  for (const file of await walk(new URL('ui/', src))) {
    if (!file.pathname.endsWith('.json')) continue
    const json = await readJson(file)
    for (const path of Object.values(json.usingComponents ?? {})) {
      assert.match(path, /^\/ui\/components\//)
      for (const extension of ['ts', 'json', 'wxml']) await access(new URL(`${path.slice(1)}.${extension}`, src))
    }
  }
})

test('infrastructure does not import services or UI modules', async () => {
  for (const file of await walk(new URL('infra/', src))) {
    if (!file.pathname.endsWith('.ts')) continue
    const source = await readFile(file, 'utf8')
    assert.doesNotMatch(source, /from ['"][^'"]*(?:services|ui)\//, file.pathname)
  }
})
