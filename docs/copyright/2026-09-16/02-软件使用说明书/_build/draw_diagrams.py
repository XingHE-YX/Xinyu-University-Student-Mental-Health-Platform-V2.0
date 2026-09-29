from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white

OUT = Path(__file__).resolve().parent
pdfmetrics.registerFont(TTFont('CN', '/Library/Fonts/Arial Unicode.ttf'))
INK, TEAL, LINE = map(HexColor, ['#1F2D2B','#2E6F68','#A9BFBA'])

def text(c,x,y,lines,size=14,center=False,color=INK):
    c.setFillColor(color); c.setFont('CN',size)
    for i,line in enumerate(lines):
        (c.drawCentredString if center else c.drawString)(x,y-i*(size+8),line)

def box(c,x,y,w,h,title,detail=(),fill='#F4F8F6'):
    c.setStrokeColor(LINE); c.setFillColor(HexColor(fill)); c.setLineWidth(1)
    c.roundRect(x,y,w,h,8,fill=1,stroke=1)
    text(c,x+w/2,y+h-27,[title],16,True,TEAL)
    text(c,x+w/2,y+h-53,list(detail),11,True)

def arrow(c,points,dashed=False):
    c.setStrokeColor(TEAL); c.setFillColor(TEAL); c.setLineWidth(1.8)
    c.setDash(5,4) if dashed else c.setDash()
    p=c.beginPath();p.moveTo(*points[0])
    for xy in points[1:]:p.lineTo(*xy)
    c.drawPath(p)
    x,y=points[-1]; px,py=points[-2]
    dx,dy=x-px,y-py; scale=(dx*dx+dy*dy)**.5;dx/=scale;dy/=scale
    p=c.beginPath();p.moveTo(x,y);p.lineTo(x-9*dx+4*dy,y-9*dy-4*dx);p.lineTo(x-9*dx-4*dy,y-9*dy+4*dx);p.close()
    c.setDash();c.drawPath(p,fill=1,stroke=0)

c=canvas.Canvas(str(OUT/'architecture.pdf'),pagesize=(1000,620))
text(c,42,579,['心语大学生心理健康平台 · 三端分层架构'],23)
text(c,42,548,['学生端与管理后台通过 Python 业务接口访问数据，外部能力经适配层接入。'],13)
box(c,40,400,220,102,'微信小程序学生端',['TypeScript · WXML · WXSS','今日 / 自测 / 树洞 / 我的'])
box(c,40,239,220,102,'桌面 Web 管理后台',['Vue 3 · TypeScript · Vite','任务处理 / 身份授权 / 审计'])
box(c,326,411,326,91,'统一 HTTP API',['FastAPI · Pydantic · /api/v1','会话认证 / 输入校验 / 统一响应'])
box(c,326,252,326,114,'业务服务与确定性规则',['同意与身份 / 心情与自测 / 树洞','安全支持 / 后台任务 / 幂等与版本校验','脱敏投影与最小必要审计'])
box(c,326,104,326,101,'本地数据与审计',['内存仓储 / 演示任务索引 / 审计记录','截图环境：仅合成数据；重启不保留记录'])
box(c,725,405,235,97,'登录与学校核验适配',['正式：微信与学校服务','本次：本地合成身份适配器'])
box(c,725,248,235,97,'受限 AI 辅助适配',['DeepSeek HTTP 调用与输出校验','本次未配置；固定结果保持可用'])
box(c,725,98,235,97,'CloudBase 数据适配',['云端文档数据库访问接口','本次未部署云环境'])
arrow(c,[(260,450),(326,450)])
arrow(c,[(260,289),(288,289),(288,425),(326,425)])
arrow(c,[(489,411),(489,366)])
arrow(c,[(489,252),(489,205)])
arrow(c,[(652,337),(688,337),(688,453),(725,453)],True)
arrow(c,[(652,295),(725,295)],True)
arrow(c,[(652,151),(725,151)],True)
text(c,42,50,['实线：本次本地运行链路。虚线：外部适配边界，按环境配置启用。'],12)
text(c,42,27,['客户端不直连数据库管理接口或 AI；用户身份、业务数据和匿名展示按服务端规则隔离。'],12)
c.save()

c=canvas.Canvas(str(OUT/'data-flow.pdf'),pagesize=(1000,560))
text(c,42,519,['业务请求与数据处理流程'],23)
text(c,42,486,['以保存记录、提交自测或提交后台决定为例，显示服务端处理顺序与失败返回路径。'],13)
boxes=[(40,350,'1  用户发起操作',['选择心情 / 答题 / 处理任务']),
       (375,350,'2  请求与认证',['请求编号 / 会话 / 输入校验']),
       (710,350,'3  业务规则校验',['同意 / 身份 / 对象状态'])]
for x,y,title,detail in boxes:box(c,x,y,250,95,title,detail)
arrow(c,[(290,397),(375,397)]);arrow(c,[(625,397),(710,397)])
box(c,710,188,250,104,'4  幂等与版本保护',['重复提交重放 / 并发冲突检查','固定计分或状态迁移'])
box(c,375,188,250,104,'5  记录与审计',['保存必要业务事实','敏感动作写入最小审计'])
box(c,40,188,250,104,'6  返回页面状态',['统一响应 / 最小展示字段','成功后刷新；失败保留重试'])
arrow(c,[(835,350),(835,292)]);arrow(c,[(710,240),(625,240)]);arrow(c,[(375,240),(290,240)])
box(c,40,40,920,93,'错误与依赖回退',['无权限、会话失效、校验失败或版本冲突：返回明确错误，不显示成功。',
    '外部 AI 不可用：保留固定规则结果；身份核验不可用：停留核验状态。'],'#FBF8F1')
arrow(c,[(500,350),(500,325),(20,325),(20,86),(40,86)],True)
c.save()
print('Created architecture.pdf and data-flow.pdf')
