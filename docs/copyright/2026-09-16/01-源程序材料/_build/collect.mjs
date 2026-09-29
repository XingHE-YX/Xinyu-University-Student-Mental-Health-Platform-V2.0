import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import * as prettier from '../../../../../admin/node_modules/prettier/index.mjs';
import { parse } from '../../../../../admin/node_modules/@babel/parser/lib/index.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../../..');
const hash = (s) => crypto.createHash('sha256').update(s).digest('hex');
const split = (s) => s.replace(/\r\n/g, '\n').replace(/\n$/, '').split('\n');
const candidates = [];
async function walk(folder, allowed) {
  for (const e of await fs.readdir(path.join(root, folder), { withFileTypes: true })) {
    const rel = `${folder}/${e.name}`;
    if (['node_modules', 'tests', 'miniprogram_npm', '__pycache__'].includes(e.name)) continue;
    if (e.isDirectory()) await walk(rel, allowed);
    else if (allowed.includes(path.extname(e.name)) &&
      !/\.(test|spec)\./.test(e.name) &&
      !['package-lock.json','package.json','project.config.json','project.private.config.json','tsconfig.json'].includes(e.name)) candidates.push(rel);
  }
}
await walk('miniprogram', ['.ts', '.wxml', '.wxss', '.json']);
await walk('admin/src', ['.ts', '.vue', '.css']);
await walk('backend/app', ['.py']);
candidates.push('backend/scf_bootstrap');
const order = [];
const add = (p) => { if (candidates.includes(p) && !order.includes(p)) order.push(p); };
// A declared, reproducible whole-program file order. Files are never sampled internally.
['miniprogram/app.ts', 'admin/src/main.ts', 'admin/src/App.vue', 'backend/app/main.py'].forEach(add);
const appConfig = JSON.parse(await fs.readFile(path.join(root, 'miniprogram/app.json'), 'utf8'));
appConfig.pages.forEach((p) => add(`miniprogram/${p}.ts`));
candidates.filter(p => p.startsWith('miniprogram/')).sort().forEach(add);
candidates.filter(p => p.startsWith('admin/')).sort().forEach(add);
const tail = ['backend/app/services/safety_service.py', 'backend/app/services/treehole_service.py', 'backend/app/services/admin_workbench_service.py'];
candidates.filter(p => p.startsWith('backend/') && !tail.includes(p)).sort().forEach(add);
tail.forEach(add);
if (order.length !== candidates.length) throw new Error('Source inventory mismatch');
const records = [];
let transpileChecks = 0;
for (const rel of order) {
  const raw = await fs.readFile(path.join(root, rel));
  const original = raw.toString('utf8');
  let formatted = original;
  const ext = path.extname(rel);
  const parser = { '.ts': 'typescript', '.vue': 'vue', '.css': 'css', '.wxss': 'css', '.json': 'json', '.wxml': 'html' }[ext];
  if (parser) {
    formatted = await prettier.format(original, { parser, printWidth: 86, tabWidth: 2, semi: true, singleQuote: true, htmlWhitespaceSensitivity: 'strict', endOfLine: 'lf' });
  }
  if (ext === '.ts' && !rel.endsWith('.d.ts')) {
    const clean = (v) => {
      if (v?.type === 'TSParenthesizedType') return clean(v.typeAnnotation);
      if (Array.isArray(v)) return v.filter(x => x?.type !== 'EmptyStatement').map(clean);
      if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).filter(([k]) => !['start','end','loc','extra','comments','leadingComments','trailingComments','innerComments'].includes(k)).map(([k,x]) => [k,clean(x)]));
      return v;
    };
    const normalize = (s) => JSON.stringify(clean(parse(s, { sourceType: 'module', plugins: ['typescript'] })));
    if (normalize(original) !== normalize(formatted)) throw new Error(`TypeScript AST mismatch: ${rel}`);
    transpileChecks++;
  }
  for (const [folder, value] of [['original', raw], ['formatted', formatted]]) {
    const dest = path.join(here, folder, rel);
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.writeFile(dest, value);
  }
  records.push({ path: rel, original_sha256: hash(raw), formatted_sha256: hash(formatted),
    original_lines: original ? split(original).length : 0,
    original_nonblank: split(original).filter(s => s.trim()).length,
    formatted_lines: formatted ? split(formatted).length : 0,
    formatted_nonblank: split(formatted).filter(s => s.trim()).length,
    lines: formatted ? split(formatted) : [] });
}
const payload = { root, created_at: new Date().toISOString(), commit: execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),
  source: 'current working tree, including uncommitted edits', formatter: `prettier ${prettier.version}; Python and shell unchanged`,
  transpile_checks: transpileChecks, records };
await fs.writeFile(path.join(here, 'source-data.json'), JSON.stringify(payload, null, 2));
console.log(JSON.stringify({ files: records.length, original_lines: records.reduce((a,r)=>a+r.original_lines,0), original_nonblank: records.reduce((a,r)=>a+r.original_nonblank,0), formatted_lines: records.reduce((a,r)=>a+r.formatted_lines,0), formatted_nonblank: records.reduce((a,r)=>a+r.formatted_nonblank,0), transpile_checks: transpileChecks,
  beginning: records.slice(0,24).map(r=>[r.path,r.formatted_nonblank]), end: records.slice(-3).map(r=>[r.path,r.formatted_nonblank]) }, null, 2));
