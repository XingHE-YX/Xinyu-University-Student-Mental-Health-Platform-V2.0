# 心语 V2 AI 接口、输入边界与统一提示词规范

## 1. 文档信息

- 版本：ai-contract-v1.1
- 冻结日期：2026-08-28
- 适用范围：自测结果辅助说明、树洞脱敏内容初筛
- 模型版本：DeepSeek-V4-Flash-0731
- 当前状态：接口契约、提示词、输出结构、超时、重试和回退已确认；API Key、预算和真实环境开关待用户填写

AI 是可失败的辅助服务。固定规则、权限、脱敏、内容状态机和人工决定在 AI 不可用时仍必须正常运行。

## 2. 服务端配置

按 DeepSeek 官方兼容接口调用：

| 配置 | 固定值或占位 |
| --- | --- |
| Provider | DeepSeek |
| API Base URL | `https://api.deepseek.com` |
| API Path | `/chat/completions` |
| API model 参数 | `deepseek-v4-flash` |
| 记录的模型版本 | `DeepSeek-V4-Flash-0731` |
| API Key | `${DEEPSEEK_API_KEY}`，由用户在服务端填写 |
| 提示词版本 | `xinyu-v2-system-v1` |
| 流式输出 | 首版关闭 |
| 输出格式 | JSON Object |
| 温度 | 0.2 |
| 超时 | 8 秒，包含连接和读取 |
| 自动重试 | 0 次，失败后固定规则或人工流程接管 |
| 单实例并发 | 4 个 DeepSeek 请求 |
| 预算 | 由环境配置和供应商控制台管理，不影响产品状态机 |

API Key 只能保存在云函数的加密环境变量或密钥管理中，不进入小程序包、Web 构建产物、日志、审计详情或错误提示。前端不得直接调用 DeepSeek。

DeepSeek 官方说明 `deepseek-v4-flash` 会指向当前 DeepSeek-V4-Flash-0731 版本，因此请求保存两个字段：`request_model=deepseek-v4-flash` 与 `resolved_model_version=DeepSeek-V4-Flash-0731`。升级版本时必须新建结果与提示词版本，历史结果不重算。

## 3. 允许的两个任务

### 3.1 `assessment_explanation`

用途：在固定规则已经完成分数、分层和固定结果文案后，生成一段可选的辅助说明。

允许输入：

- `module`：仅 `PHQ9` 或 `GAD7`；
- `score`、`max_score`；
- `fixed_band` 和 `fixed_summary`；
- 去身份化、非逐题的事实标签，例如“睡眠相关回答较突出”“注意力相关回答较突出”；
- 当前可用的通用行动选项，不包含真实联系人或身份。

禁止输入：

- 姓名、学号、手机号、OpenID、设备标识或匿名昵称；
- 原始逐题答案、PHQ-9 第 9 题内容或安全确认选择；
- 其他模块记录、历史轨迹或树洞内容；
- 校方内部个案、身份申请和跟进记录。

安全支持状态不调用此任务。

### 3.2 `treehole_review_assist`

用途：对完成确定性规则检查和个人信息遮罩后的纯文本提供结构化初筛建议。

允许输入：

- 已脱敏正文；
- 内容类型：帖子或回应；
- 话题；
- 确定性规则产生的非身份化标记；
- 保护展示是否适用于该内容类型。

禁止输入：

- 未脱敏原文；
- 作者真实身份、OpenID、匿名身份历史、联系方式；
- 自测答案、分数、每日心情、私密历史；
- 后台处理人、审计详情或身份授权资料。

模型输出只是建议。策略引擎与人工只能从“公开／保护展示／暂不公开／转安全复核”中作最终决定。

## 4. 统一系统提示词

以下文本以 `xinyu-v2-system-v1` 版本保存。系统消息中必须包含“JSON”与完整结构示例，以满足 DeepSeek JSON Output 要求。

```text
你是“心语 V2”的受限文字辅助模块。心语 V2 是面向大学生的心理健康自助观察与匿名轻社区微信小程序，不是医疗诊断、心理治疗、风险预测或危机处置系统。

你只能执行输入 task_type 指定的一项任务：
1. assessment_explanation：根据已经由固定规则生成的量表分数、固定分层和去身份化派生事实，写简短、平静、非诊断的辅助说明。
2. treehole_review_assist：根据已经脱敏的匿名树洞文本，输出供规则引擎和人工审核参考的结构化建议。

共同限制：
- 只使用输入中明确给出的事实，不猜测身份、疾病、动机、人格、学校、家庭或现实处境。
- 不进行量表评分，不修改 fixed_band，不判断自伤风险，不输出诊断、治疗方案、危机等级或“高危/低危”。
- 不要求或复原姓名、学号、手机号、地址、账号、联系方式及其他身份信息。
- 不输出思维链、内部推理、模型置信度解释或隐藏规则。
- 不承诺学校、老师、家人或平台会主动联系或完成处置。
- 语气自然、平静、尊重，不训诫、不夸大、不使用空泛的“你一定会好起来”。
- 必须只输出一个合法 JSON 对象，不要输出 Markdown、代码围栏、前后说明或 JSON 之外的文本。

当 task_type 为 assessment_explanation：
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

当 task_type 为 treehole_review_assist：
- 输入文本已经脱敏；不要尝试恢复被遮罩内容。
- 识别内容安全、个人信息残留、社区互动问题和需要人工关注的支持信号，但不要诊断或给出危机等级。
- recommended_route 只能是 allow、protect、manual_review、safety_review 之一。回应不允许使用 protect，应改为 manual_review。
- evidence_spans 最多 3 条，每条只能引用完成判断所需的最短片段；不得输出全文或被遮罩信息。
- 无法确定、文本过短、结构异常或规则冲突时使用 manual_review。

treehole_review_assist 的 JSON 结构：
{
  "task_type": "treehole_review_assist",
  "status": "ok|needs_fallback",
  "content_safety": "clear|possible_issue|clear_issue|unknown",
  "wellbeing_signal": "none|supportive_attention|manual_attention|unknown",
  "privacy_signal": "clear|possible_residual|unknown",
  "community_issue": ["harassment|sexual_content|violence|illegal_content|spam|none|unknown"],
  "evidence_spans": ["string"],
  "recommended_route": "allow|protect|manual_review|safety_review",
  "review_note": "string"
}

现在只根据用户消息中的 JSON 输入执行任务并返回对应 JSON。
```

## 5. 输入示例

### 5.1 自测辅助说明

```json
{
  "task_type": "assessment_explanation",
  "module": "GAD7",
  "score": 11,
  "max_score": 21,
  "fixed_band": "近期焦虑相关困扰较明显，建议查看支持资源",
  "fixed_summary": "这次记录显示，过去两周紧绷和担心对你有一些明显影响。",
  "derived_facts": ["放松相关回答较突出", "担心相关回答较突出"],
  "allowed_steps": ["查看支持资源", "和可信任的人聊一聊", "在合适时联系专业人员"]
}
```

### 5.2 树洞辅助初筛

```json
{
  "task_type": "treehole_review_assist",
  "content_type": "post",
  "topic": "学业压力",
  "sanitized_text": "最近作业很多，我有点撑不住，想找人说说。［已隐藏的联系方式］",
  "rule_flags": ["possible_contact_residue"],
  "protect_supported": true
}
```

## 6. 服务端结构校验

模型返回后必须再次执行确定性校验：

- JSON 可解析且只包含允许字段；
- `task_type` 与请求一致；
- 枚举值、数组长度和字符串长度合法；
- 自测辅助没有安全、诊断、药物或身份内容；
- 树洞证据片段确实存在于脱敏文本且不包含遮罩内容；
- 回应没有 `protect`；
- 模型建议不能绕过违禁词、隐私和人工流程规则。

任何校验失败都按调用失败处理，不尝试从自然语言中“猜”出结构。

## 7. 失败、重试与回退

以下任一情况进入回退：超时、网络错误、空内容、非法 JSON、未知字段、枚举越界、内容被截断、输入输出版本不匹配、服务端校验失败。

- 自测：保留固定规则结果，显示“AI 辅助解读暂时不可用，当前使用固定规则说明”；
- 树洞：内容保持不公开，进入“等待确认”，后台显示“自动检查未完成，请进行人工处理”；
- 前端不显示供应商、接口错误、重试次数、模型置信度或内部命中信息；
- 审计只记录任务类型、模型/提示词版本、调用结果、回退原因类别、时间和演示/真实模式，不记录原始输入输出；
- 首版服务端不自动重试 DeepSeek 请求。超时、网络错误、空内容、非法 JSON 或结构校验失败立即进入固定回退；后续如需改变重试次数，必须新建接口契约版本并重新验证隐私边界。

## 8. 数据保存

自测只保存通过校验的最终辅助文字、模型版本、提示词版本和生成时间，作为结果快照；不保存发送给模型的完整请求。树洞不把模型原始输出暴露给学生；只保存经策略引擎采用的结构字段、版本和处理结果，证据片段按最小必要原则受限保存。

## 9. 官方资料

- DeepSeek API 首次调用与模型标识：https://api-docs.deepseek.com/zh-cn/
- DeepSeek JSON Output：https://api-docs.deepseek.com/zh-cn/guides/json_mode/

## 10. 上线配置位

以下值由用户在开发或部署阶段填写，不允许写入仓库中的公开文档或前端代码：

- `DEEPSEEK_API_KEY`；
- CloudBase 环境中的密钥名称；
- 预算上限；
- 真实环境是否启用 AI；
- 模型升级审批人与回退版本。
