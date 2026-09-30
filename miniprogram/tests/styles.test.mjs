import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import { test } from 'node:test'
import postcss from 'postcss'
import selectorParser from 'postcss-selector-parser'

const src = new URL('../src/', import.meta.url)
const read = (path) => readFile(new URL(path, src), 'utf8')
const names = (css) => {
  const classes = new Set()
  css.walkRules((rule) => selectorParser((tree) => {
    tree.walkClasses((node) => classes.add(node.value))
  }).processSync(rule.selector))
  return classes
}
const bem = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:__[a-z0-9]+(?:-[a-z0-9]+)*)?(?:--[a-z0-9]+(?:-[a-z0-9]+)*)?$/

test('shared styles contain only universal page rules used by every page', async () => {
  const shared = await read('ui/shared/styles/global.wxss')
  const css = postcss.parse(shared)
  const classes = names(css)
  assert.deepEqual([...classes].sort(), ['app-page', 'app-page--padded'])
  css.walkAtRules((rule) => assert.equal(rule.name, 'media'))
  css.walkRules((rule) => assert.ok(rule.selector === 'page' || rule.selector === '.app-page' || rule.selector === '.app-page--padded'))
  const app = JSON.parse(await read('app.json'))
  for (const page of app.pages) {
    const markup = await read(`${page}.wxml`)
    for (const name of classes) assert.ok(markup.includes(name), `${page}: ${name}`)
  }
})

test('each page and component owns its BEM selectors and imports no foreign styles', async () => {
  for (const kind of ['pages', 'components']) {
    for (const entry of await readdir(new URL(`ui/${kind}/`, src), { withFileTypes: true })) {
      if (!entry.isDirectory()) continue
      const block = kind === 'pages' ? `page-${entry.name}` : entry.name
      const css = postcss.parse(await read(`ui/${kind}/${entry.name}/index.wxss`))
      const classes = names(css)
      css.walkAtRules('import', () => assert.fail(`${block} must bundle its styles`))
      for (const name of classes) {
        assert.match(name, bem)
        assert.ok(name === block || name.startsWith(`${block}__`) || name.startsWith(`${block}--`), `${block}: ${name}`)
      }
      const markup = await read(`ui/${kind}/${entry.name}/index.wxml`)
      for (const attribute of markup.matchAll(/class="([^"]*)"/g)) {
        const literal = attribute[1].replace(/{{[\s\S]*?}}/g, '')
        for (const name of literal.trim().split(/\s+/).filter(Boolean)) {
          assert.match(name, bem)
          assert.ok(name.startsWith(block) || (kind === 'pages' && ['app-page', 'app-page--padded'].includes(name)), `${block}: ${name}`)
        }
        for (const expression of attribute[1].matchAll(/{{([\s\S]*?)}}/g)) {
          for (const literal of expression[1].matchAll(/'([^']*)'/g)) {
            for (const name of literal[1].split(/\s+/).filter((value) => value.includes('__') || value.includes('--'))) {
              assert.ok(name.startsWith(block), `${block}: ${name}`)
              assert.ok(classes.has(name), `${block}: missing state style ${name}`)
            }
          }
        }
      }
      for (const expression of markup.matchAll(/{{([\s\S]*?)}}/g)) {
        assert.doesNotThrow(() => new Function(`return (${expression[1]})`), `${block}: ${expression[1]}`)
      }
    }
  }
})

test('main-page native-tab spacing stays local and selected options have local declarations', async () => {
  for (const name of ['today', 'assessment-center', 'treehole', 'my']) {
    const css = postcss.parse(await read(`ui/pages/${name}/index.wxss`))
    let rule
    css.walkRules(`.page-${name}--main`, (value) => { rule = value })
    assert.ok(rule)
    assert.ok(rule.nodes.some((node) => node.prop === 'padding-bottom' && node.value === '32px'))
  }
  for (const name of ['question-option', 'mood-picker']) {
    const css = postcss.parse(await read(`ui/components/${name}/index.wxss`))
    assert.ok([...names(css)].some((value) => value.endsWith('--selected')))
  }
})
