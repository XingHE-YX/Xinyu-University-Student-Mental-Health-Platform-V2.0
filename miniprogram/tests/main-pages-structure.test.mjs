import assert from 'node:assert/strict'
import { access, readFile } from 'node:fs/promises'
import { test } from 'node:test'

const root = new URL('../src/', import.meta.url)

async function read(relativePath) {
  return readFile(new URL(relativePath, root), 'utf8')
}

test('main pages use the native tab bar as their only bottom navigation', async () => {
  const app = JSON.parse(await read('app.json'))
  assert.equal(app.tabBar.list.length, 4)
  assert.deepEqual(app.tabBar.list.map((item) => item.text), ['今日', '自测', '树洞', '我的'])
  for (const item of app.tabBar.list) {
    await access(new URL(item.iconPath, root))
    await access(new URL(item.selectedIconPath, root))
  }

  for (const page of ['today', 'assessment-center', 'treehole', 'my']) {
    const wxml = await read(`ui/pages/${page}/index.wxml`)
    assert.doesNotMatch(wxml, /<bottom-nav\b/)
  }
})

test('the page container layout is available globally', async () => {
  const appWxss = await read('app.wxss')
  assert.match(appWxss, /\.page-container\s*\{/)
  assert.match(appWxss, /\.page-container--padded\s*\{/)
})

test('main pages expose the reading-first design structure', async () => {
  const expectedMarkers = {
    today: ['今日', '此时此刻', '最近的自我观察'],
    'assessment-center': ['自测', '把最近的状态记下来', 'item.title'],
    treehole: ['树洞', '想先读一会儿也可以', '全部话题'],
    my: ['我的', '在树洞中的身份', '我的树洞内容'],
  }

  for (const [page, markers] of Object.entries(expectedMarkers)) {
    const wxml = await read(`ui/pages/${page}/index.wxml`)
    for (const marker of markers) assert.match(wxml, new RegExp(marker))
  }
})

test('today mood entry follows the six-option bottom-sheet flow', async () => {
  const wxml = await read('ui/pages/today/index.wxml')
  const moodService = await read('services/mood.ts')
  assert.match(wxml, /记录此刻/)
  assert.match(wxml, /showMoodSheet/)
  assert.match(wxml, /mood-sheet__error/)
  assert.match(wxml, /稍后再说/)
  assert.match(wxml, /已记下此刻/)
  assert.match(wxml, /再看一眼/)
  for (const label of ['愉快', '平静', '疲惫', '焦虑', '低落', '烦躁']) assert.match(moodService, new RegExp(label))
})

test('the account page provides identity recovery and logout actions', async () => {
  const wxml = await read('ui/pages/my/index.wxml')
  assert.match(wxml, /完成身份核验/)
  assert.match(wxml, /pages\/identity-verification\/index\?from=my/)
  assert.match(wxml, /退出登录/)
  assert.match(wxml, /bindtap="logout"/)
})

test('support resource views disclose placeholder availability and source', async () => {
  for (const path of [
    'ui/pages/support-resources/index.wxml',
    'ui/components/support-resource-list/index.wxml',
  ]) {
    const wxml = await read(path)
    assert.match(wxml, /item\.availabilityText/)
    assert.match(wxml, /item\.sourceText/)
  }
})
