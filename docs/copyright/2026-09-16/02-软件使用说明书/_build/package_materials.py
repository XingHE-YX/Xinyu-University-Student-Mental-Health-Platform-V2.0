from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import csv
import hashlib
import json

HERE=Path(__file__).resolve().parent
MANUAL=HERE.parent
BASE=MANUAL.parent
CODE=BASE/'01-源程序材料'
ROOT=HERE.parents[5]
manifest=json.loads((CODE/'_build/manifest.json').read_text())
figures=json.loads((HERE/'figure-index.json').read_text())
validation=json.loads((HERE/'manual-validation.json').read_text())

readme=f'''软著材料：任务1与任务2

软件暂用名称：心语大学生心理健康平台
登记版本暂用：V1.0
代码项目：XinYu-V2

1. 任务1：源程序Word材料，共60页，连续前30页、后30页，每页至少50行代码。
   本次源码快照共{manifest['source_files']}个程序文件，原始物理行数{manifest['original_physical_lines']}行。
   说明书联调修复已同步到源程序Word、源码快照和文件清单。
2. 任务2：使用说明书Word，共{validation['pages']}页，包含45张实际界面截图、2张架构/数据流程图、50个后端接口及源码模块索引。
3. 预览PDF用于核对排版；正式编辑使用Word文件。截图原图与OpenAPI定义一并提供。

本地验证：后端、Web后台均已启动；小程序使用微信开发者工具和官方自动化接口完成实际页面流程。
登录、学校身份与帖子任务为合成测试数据；后端使用内存仓储。正式CloudBase、学校核验、真实微信登录与外部AI未在本次完成生产接入。
后台使用独立预置演示任务，不应将其与截图中新发帖子描述为同一条已联通的审核记录。
单条删除和演示重置采集到确认步骤后保留取证数据，未执行最终删除或重置。

核对结果：45页说明书无空白页，47幅图与图注同页且编号连续；嵌入图像与原图哈希一致。
源程序PDF仍为60页，并逐行核对Word/PDF文本与排版源码一致，末页完整结束后台工作台模块。
小程序19项测试、类型检查与真实HTTP业务流程检查通过；本地配置的4个环境边界用例通过。

名称与版本沿用上一份材料的暂用值，正式提交前须与申请表统一。任务3登记申请表尚未填写。
本地复现入口见完整源码包内 deploy/local/README.md。
'''
(BASE/'材料核对说明.txt').write_text(readme)
with (MANUAL/'截图与图号索引.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['图号','图注','原文件','SHA256'])
    for item in figures:
        p=(HERE if item['file'] in ('architecture.png','data-flow.png') else MANUAL/'截图')/item['file']
        w.writerow([item['figure'],item['caption'],item['file'],hashlib.sha256(p.read_bytes()).hexdigest()])

dest=BASE/'心语软著材料_任务1与任务2.zip'
with ZipFile(dest,'w',ZIP_DEFLATED) as z:
    z.write(BASE/'材料核对说明.txt','材料核对说明.txt')
    for p in CODE.iterdir():
        if p.is_file() and p.suffix in ('.docx','.pdf','.csv','.zip'):z.write(p,'01-源程序材料/'+p.name)
    for folder in ('original','formatted'):
        for p in (CODE/'_build'/folder).rglob('*'):
            if p.is_file():z.write(p,'01-源程序材料/'+str(p.relative_to(CODE)))
    for name in ('manifest.json','validation.json','完整源程序编排.txt'):
        z.write(CODE/'_build'/name,'01-源程序材料/_build/'+name)
    for p in MANUAL.iterdir():
        if p.is_file() and p.suffix in ('.docx','.pdf','.csv'):z.write(p,'02-软件使用说明书/'+p.name)
    for p in sorted((MANUAL/'截图').glob('*.png')):z.write(p,'02-软件使用说明书/截图/'+p.name)
    for name in ('architecture.png','data-flow.png','architecture.pdf','data-flow.pdf'):
        z.write(HERE/name,'02-软件使用说明书/架构与流程图/'+name)
    for name in ('openapi.json','endpoint-index.json','figure-index.json','manual-validation.json'):
        z.write(HERE/name,'02-软件使用说明书/_build/'+name)
with ZipFile(dest) as z:
    assert z.testzip() is None
    print(json.dumps({'archive':str(dest),'entries':len(z.namelist()),'bytes':dest.stat().st_size},ensure_ascii=False,indent=2))
