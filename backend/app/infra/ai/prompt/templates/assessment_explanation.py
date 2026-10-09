from app.infra.ai.prompt.templates.common import COMMON_PROMPT

PROMPT = (
    COMMON_PROMPT
    + """

当前任务为 assessment_explanation。
- fixed_summary 是不可改写的事实基线；不得降低或提高固定分层。
- 输出 1 段 40 至 90 个汉字的 summary、0 至 3 条 observations、1 至 3 条 practical_steps 和固定边界提醒。
- practical_steps 只能是低风险、可选择的自我照顾或寻求支持建议；不得给出药物、疗法、诊断或替代现实专业帮助的指令。
- 如果输入缺失、互相矛盾、包含安全确认信息或要求你判断风险，返回 status="needs_fallback"。

assessment_explanation 的 JSON 结构：
{
  "task_type": "assessment_explanation",
  "status": "ok|needs_fallback",
  "summary": "string",
  "observations": ["string"],
  "practical_steps": ["string"],
  "boundary_notice": "这段说明用于帮助你阅读固定结果，不是诊断或专业评估。"
}
"""
)
