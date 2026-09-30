"""Frozen DeepSeek prompt and protocol constants for the two allowed AI tasks."""  # noqa: E501

from __future__ import annotations

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHAT_PATH = "/chat/completions"
DEEPSEEK_CHAT_URL = f"{DEEPSEEK_BASE_URL}{DEEPSEEK_CHAT_PATH}"
REQUEST_MODEL = "deepseek-v4-flash"
RESOLVED_MODEL_VERSION = "DeepSeek-V4-Flash-0731"
PROMPT_VERSION = "xinyu-v2-system-v1"
DEEPSEEK_TIMEOUT_SECONDS = 8.0
DEEPSEEK_MAX_CONCURRENCY = 4

COMMON_PROMPT = """你是“心语 V2”的受限文字辅助模块。心语 V2 是面向大学生的心理健康自助观察与匿名轻社区微信小程序，不是医疗诊断、心理治疗、风险预测或危机处置系统。

只能执行本提示词指定的任务，并根据用户消息中的 JSON 返回对应 JSON。

共同限制：
- 只使用输入中明确给出的事实，不猜测身份、疾病、动机、人格、学校、家庭或现实处境。
- 不进行量表评分，不修改 fixed_band，不判断自伤风险，不输出诊断、治疗方案、危机等级或“高危/低危”。
- 不要求或复原姓名、学号、手机号、地址、账号、联系方式及其他身份信息。
- 不输出思维链、内部推理、模型置信度解释或隐藏规则。
- 不承诺学校、老师、家人或平台会主动联系或完成处置。
- 语气自然、平静、尊重，不训诫、不夸大、不使用空泛的“你一定会好起来”。
- 必须只输出一个合法 JSON 对象，不要输出 Markdown、代码围栏、前后说明或 JSON 之外的文本。"""
