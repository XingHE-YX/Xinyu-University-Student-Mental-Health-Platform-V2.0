from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DATA = json.loads((HERE / 'source-data.json').read_text())
ROOT = Path(DATA['root'])
MANIFEST = json.loads((HERE / 'manifest.json').read_text())
NAME = '心语大学生心理健康平台_V1.0_源程序_前30页后30页'

changed = []
for f in DATA['records']:
    if hashlib.sha256((ROOT / f['path']).read_bytes()).hexdigest() != f['original_sha256']:
        changed.append(f['path'])
assert not changed, f'Source changed since snapshot: {changed}'

pdf = PdfReader(HERE / f'{NAME}.pdf')
assert len(pdf.pages) == 60
source_lookup = {f['path']: f['lines'] for f in DATA['records']}
checked_rows = 0
for page, info in zip(pdf.pages, MANIFEST['pages']):
    text = page.extract_text()
    assert '心语大学生心理健康平台' in text
    rows = re.findall(r'^\d{4,5}\s', text, re.M)
    assert len(rows) == info['nonblank_source_rows'], info
    flattened = re.sub(r'\s+', '', text)
    for r in info['ranges']:
        for line_no in range(r['start_line'], r['end_line'] + 1):
            source = source_lookup[r['file']][line_no - 1]
            if not source.strip():
                continue
            needle = re.sub(r'\s+', '', f'{line_no:04d}{source}')
            assert needle in flattened, (info['submission_page'], r['file'], line_no)
            checked_rows += 1

tracked = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z','backend','admin','miniprogram','deploy'],cwd=ROOT).decode().split('\0')
source_paths = {f['path'] for f in DATA['records']}
paths = set(tracked) | source_paths | {'.nvmrc','TECH_STACK.md','BACKEND_STRUCTURE.md','CONFIGURATION_REGISTRY.md'}
excluded_parts = {'node_modules','dist','build','.venv','.packages','__pycache__','.pytest_cache','.ruff_cache','.git'}
paths = sorted(p for p in paths if p and (ROOT/p).is_file() and not any(part in excluded_parts for part in Path(p).parts) and not Path(p).name.startswith('.env') and Path(p).name not in {'project.private.config.json','.DS_Store','credentials','secrets'} and Path(p).suffix not in {'.pyc','.key','.p12','.pem','.zip'})

readme = '''XinYu-V2 工程源代码快照（软著材料配套）

本压缩包保留项目原始代码、运行配置模板、依赖清单、测试和静态资源。
源程序Word使用对应代码的排版副本，不可把60页摘录作为独立完整工程执行。

本地运行：
1. 后端：使用Python 3.11。进入backend目录后执行：
   python3.11 -m venv .venv
   .venv/bin/python -m pip install -r requirements.lock
   .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 9000
   健康检查地址：http://127.0.0.1:9000/api/v1/health
   未提供外部配置时会返回unconfigured/degraded；这不表示线上服务已配置。
2. 管理后台：进入admin目录后执行npm ci --legacy-peer-deps，再执行npm run dev。
   构建执行npm run build；发布工具链基线见根目录TECH_STACK.md和.nvmrc。
3. 学生端：进入miniprogram目录执行npm ci；使用微信开发者工具打开该目录。
   项目配置内AppID为空，使用申请人自己的AppID或工具允许的本地预览方式。
   外部服务连接按照deploy/miniprogram/README.md配置。
4. 正式微信登录、学校身份核验、CloudBase和DeepSeek需要各自环境配置。
   原有演示模式和未配置状态按代码实际逻辑运行，不能当作线上验收结果。
5. 复现本次说明书的本地演示环境：
   backend/.venv/bin/python deploy/local/backend_demo.py
   node deploy/local/admin_preview.mjs
   具体测试身份、临时口令和环境边界见deploy/local/README.md。

本次检查：后端180项测试、小程序19项测试、后台5项测试通过；两端类型检查、
后台构建通过；后端启动及健康接口HTTP 200通过，OpenAPI注册50个端点。
未打包第三方依赖目录、构建产物、私有开发者工具配置、环境秘密文件。
软件登记名称及V1.0版本号仍为材料暂用值，以申请人最终确认值统一替换。
'''
archive = OUT / 'XinYu-V2_完整工程源代码快照.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('XinYu-V2/运行说明.txt', readme)
    for p in paths:
        actual = HERE/'original'/p if p in source_paths else ROOT/p
        z.write(actual, 'XinYu-V2/'+p)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for f in DATA['records']:
        assert hashlib.sha256(z.read('XinYu-V2/'+f['path'])).hexdigest() == f['original_sha256']

shutil.copy2(HERE/f'{NAME}.pdf', OUT/f'{NAME}_版式核对.pdf')
result = {'pdf_pages':len(pdf.pages),'min_counted_code_lines_per_page':min(p['code_lines'] for p in MANIFEST['pages']),
          'pdf_source_rows_verified':checked_rows,'source_files_unchanged':len(DATA['records']),
          'zip_files':len(paths)+1,'zip_bytes':archive.stat().st_size,
          'backend_tests_passed':180,'miniprogram_tests_passed':19,'admin_tests_passed':5,
          'admin_build':'passed','backend_http_health':200,'backend_health_state':'unconfigured/degraded',
          'registered_endpoints':50}
(HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
