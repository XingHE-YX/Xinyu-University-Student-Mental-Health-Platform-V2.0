# 心语 V2 后端结构文档

## 0. 文档信息

- 文档版本：BACKEND-1.0
- 锁定日期：2026-08-28
- 后端主语言：Python 3.11
- HTTP 框架：FastAPI 0.128.8
- 部署形态：CloudBase Python 3.11 HTTP 云函数
- 数据库：CloudBase 文档型数据库
- API 前缀：/api/v1
- 文档状态：开发前后端合同

本文定义数据库集合、字段类型、关系、权限、认证和接口契约。客户端不得通过猜测字段、修改请求体或伪造状态绕过本文规则。

## 1. 类型、命名和通用规则

### 1.1 类型

| 文档类型 | 表示方式 |
| --- | --- |
| 字符串 | string，使用 UTF-8，除非另有说明 |
| 整数 | integer，服务端校验范围 |
| 小数 | number，服务端校验精度 |
| 布尔 | boolean |
| 时间 | datetime，统一保存为 UTC，接口使用 ISO 8601 带时区字符串 |
| 空值 | null，仅在字段表明确允许时使用 |
| 对象 | object，必须符合对应子结构 |
| 数组 | array，必须标明元素结构 |
| 密文 | encrypted_string，服务端密钥管理加密后保存 |
| 摘要 | hash_string，不可逆摘要，不用于展示 |

### 1.2 通用字段

除配置快照和审计事件另有说明外，每个集合文档都必须有：

- _id：string，CloudBase 文档 ID，由服务端生成；
- created_at：datetime，首次创建时间；
- updated_at：datetime，最后一次状态变化时间；
- version：integer，从 1 开始，每次写入状态变化加 1。

接口不会把内部数据库主键、密文、摘要和内部索引全部返回给学生端。

### 1.3 状态写入

- 所有改变状态的请求都携带 object_version 或由服务端生成的对象版本条件。
- 服务端使用条件更新；版本不一致返回 409，不覆盖最新文档。
- 删除优先使用逻辑删除。物理清理由数据保留任务执行，并写入审计。
- 日期相关查询使用用户所在时区转换到 UTC 的当天起止时间；默认时区为 Asia/Shanghai。
- 列表使用游标分页，不使用客户端传入任意数据库排序字段。

## 2. 环境与服务边界

至少有两个独立 CloudBase 环境：

| 环境 | 允许数据 | 允许操作 |
| --- | --- | --- |
| 演示环境 | 固定演示学生、固定后台账号、合成帖子、合成任务 | 可以重置，不能访问真实环境 |
| 真实授权环境 | 真实学生和经过授权的资源 | 不允许演示重置，必须有学校和隐私授权 |

环境 ID、数据库、函数配置、支持资源、后台域名和密钥完全分离。DEMO_MODE 不是数据隔离的唯一依据，服务端还必须校验 CloudBase 环境 ID。

服务组成：

1. Python HTTP 函数：接收所有学生端和后台业务 API。
2. 文档数据库访问适配器：只在后端使用 CloudBase HTTP API 凭据。
3. 微信登录适配器：服务端交换微信一次性登录凭证。
4. 学校身份核验适配器：真实环境配置后才能返回核验成功。
5. DeepSeek 适配器：只接受脱敏、白名单任务。
6. 审计写入器：每次受限读取和状态变更写入只读审计。

## 3. 数据库集合和字段

以下集合名固定使用小写下划线。CloudBase 文档型数据库不提供本项目意义上的跨集合外键约束，关系由服务端 ID 字段和业务事务顺序维护；删除或失效时由服务端检查引用。

### 3.1 user_accounts：学生账户

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 学生内部账户 ID |
| auth_subject_hash | hash_string | 是 | 微信身份主体摘要，唯一，不保存原始主体 |
| status | string | 是 | active、recovery_pending、stopped、purged |
| base_consent_status | string | 是 | accepted、not_accepted |
| base_consent_version | string | 否 | 最近一次基础服务同意版本 |
| base_consent_at | datetime | 否 | 基础服务同意时间 |
| community_consent_status | string | 是 | accepted、withdrawn、not_accepted |
| community_consent_version | string | 否 | 最近一次社区同意版本 |
| community_consent_at | datetime | 否 | 最近一次社区同意或重新同意时间 |
| identity_record_id | string | 否 | identity_records 的内部 ID |
| anonymous_identity_id | string | 否 | anonymous_identities 的内部 ID |
| stop_requested_at | datetime | 否 | 停止使用账户时间 |
| recovery_deadline_at | datetime | 否 | 停止后的 30 天恢复截止时间 |
| purged_at | datetime | 否 | 账户完成清理或不可识别化时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

关系：一个账户最多关联一个身份记录和一个当前匿名身份，可关联多条心情、自测、帖子、回应和同意事件。

### 3.2 auth_sessions：会话

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 会话 ID |
| subject_type | string | 是 | student、admin |
| subject_id | string | 是 | user_accounts 或 admin_accounts 的内部 ID |
| access_token_hash | hash_string | 是 | 短期访问令牌摘要 |
| refresh_token_hash | hash_string | 否 | 轮换刷新令牌摘要 |
| status | string | 是 | active、revoked、expired |
| access_expires_at | datetime | 是 | 访问令牌到期时间 |
| refresh_expires_at | datetime | 否 | 刷新令牌到期时间 |
| last_seen_at | datetime | 是 | 最近活动时间 |
| device_hash | hash_string | 否 | 设备摘要，仅用于异常会话提示 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

访问令牌不明文入库。学生访问令牌有效期 15 分钟，刷新令牌有效期 30 天并且每次使用后轮换；后台访问令牌有效期 15 分钟，刷新令牌有效期 8 小时。退出、改密或环境切换立即撤销会话。

### 3.3 identity_records：身份核验记录

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 身份记录 ID |
| user_id | string | 是 | user_accounts 内部 ID |
| verification_status | string | 是 | not_started、pending、verified、failed、unavailable |
| student_name_ciphertext | encrypted_string | 否 | 加密姓名，只有身份域可解密 |
| student_number_ciphertext | encrypted_string | 否 | 加密学号，只有身份域可解密 |
| provider_reference_hash | hash_string | 否 | 学校核验系统返回引用的摘要 |
| verified_at | datetime | 否 | 核验成功时间 |
| failed_reason_code | string | 否 | 内部失败码，不向学生原样返回 |
| access_version | integer | 是 | 身份访问版本，每次授权变化加 1 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

真实姓名和学号绝不进入树洞、AI 请求、普通后台任务列表或普通结果接口。学生端只接收 verified 或未核验的状态，不接收密文。

### 3.4 consent_records：同意事件

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 事件 ID |
| user_id | string | 是 | 学生账户 ID |
| consent_kind | string | 是 | base_service、community_content |
| action | string | 是 | accepted、withdrawn |
| document_version | string | 是 | 同意文档版本 |
| source | string | 是 | mini_program、admin_seed、migration |
| occurred_at | datetime | 是 | 事件发生时间 |
| request_id | string | 是 | 触发请求编号 |
| created_at | datetime | 是 | 写入时间 |
| updated_at | datetime | 是 | 同事件更新时间，事件原则上不更新 |
| version | integer | 是 | 固定为 1 |

同意事件只追加不修改。账户当前同意状态由 user_accounts 保存，完整历史由本集合保存。

### 3.5 anonymous_identities：匿名身份

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 匿名身份 ID |
| user_id | string | 是 | 学生账户 ID |
| display_name | string | 是 | 树洞展示名，不得包含真实姓名学号 |
| generation_version | string | 是 | 匿名名称生成规则版本 |
| status | string | 是 | active、retired |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

帖子只保存 anonymous_identity_id 的快照引用和必要展示名，不把身份记录 ID 返回给公开接口。

### 3.6 daily_mood_records：每日心情

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 记录 ID |
| user_id | string | 是 | 学生账户 ID |
| record_date | string | 是 | Asia/Shanghai 日期，格式 YYYY-MM-DD |
| mood_code | string | 是 | 固定心情选项枚举 |
| source | string | 是 | mini_program |
| deleted_at | datetime | 否 | 单条删除时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 最近修改时间 |
| version | integer | 是 | 乐观锁版本 |

唯一约束：user_id 加 record_date。每日心情只对本人可读，不触发审核、安全任务或 AI 请求。

### 3.7 assessment_modules：自测模块配置

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 配置 ID |
| module_code | string | 是 | phq9、gad7、sleep_observation |
| title | string | 是 | 学生端显示名称 |
| description | string | 是 | 非诊断用途说明 |
| expected_minutes | integer | 是 | 预计耗时 |
| current_questionnaire_version | string | 是 | 当前题目版本 |
| enabled | boolean | 是 | 是否允许新建会话 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 配置版本 |

固定模块只有 PHQ-9、GAD-7 和睡眠观察。后续增加模块必须另行评审，不得仅向集合写入一行就暴露给客户端。

### 3.8 assessment_questionnaires：题目和规则配置

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 题卷配置 ID |
| module_code | string | 是 | phq9、gad7、sleep_observation |
| questionnaire_version | string | 是 | 题卷版本 |
| questions | array[object] | 是 | 固定顺序的题目数组 |
| score_rule | object | 是 | 服务端规则配置；睡眠为观察映射 |
| non_diagnostic_copy_version | string | 是 | 结果说明版本 |
| enabled | boolean | 是 | 是否为可开始版本 |
| published_at | datetime | 否 | 发布时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 配置版本 |

题目对象固定字段：question_key 为 string、order 为 integer、text 为 string、options 为 array[object]。选项对象固定字段：option_key 为 string、label 为 string、score 为 integer。睡眠观察可以使用 observation_code，但不生成医学总分。

PHQ-9 和 GAD-7 的分数、较高分数展示规则和 PHQ-9 第 9 题分支由服务端配置版本决定；客户端不能提交自己的 score_rule。

当前首版评分规则必须按以下边界种子化，边界改变必须提升 scoring_rule_version：

| 模块 | 分数范围 | 普通或较高分数展示区间 |
| --- | --- | --- |
| PHQ-9 | 0–27 | 0–4、5–9、10–14、15–19、20–27 |
| GAD-7 | 0–21 | 0–4、5–9、10–14、15–21 |
| 睡眠观察 | 无总分 | 只生成作息节律、睡前阻力、恢复与日间影响三个观察维度 |

PHQ-9 影响题不计分；第 9 题同时进入总分并生成独立的 safety_triggered。睡眠第 2 题只提供实际时长事实，第 8 题只补充原因；睡眠答案不能转换为医学总分、临床等级或安全判断。

### 3.9 assessment_sessions：自测会话

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 会话 ID |
| user_id | string | 是 | 学生账户 ID |
| module_code | string | 是 | phq9、gad7、sleep_observation |
| questionnaire_version | string | 是 | 开始时冻结的题卷版本 |
| state | string | 是 | in_progress、completed、abandoned、expired |
| answers | array[object] | 否 | 仅在允许生成最终结果时保存的服务端答案快照；in_progress、abandoned、expired 和未完成安全确认时为 null |
| answered_count | integer | 否 | 仅在最终完成时记录；未完成会话不保存答题进度 |
| safety_triggered | boolean | 是 | PHQ-9 第 9 题是否非零 |
| safety_confirmation_state | string | 否 | can_be_safe、uncertain、cannot_be_safe |
| safety_resource_version | string | 否 | 已展示的安全支持资源版本 |
| safety_resource_acknowledged_at | datetime | 否 | 用户端确认资源已展示的时间，不代表用户已安全 |
| client_idempotency_key | string | 是 | 创建或完成请求幂等键 |
| started_at | datetime | 是 | 开始时间 |
| completed_at | datetime | 否 | 完成时间 |
| abandoned_at | datetime | 否 | 放弃时间 |
| expires_at | datetime | 是 | 未完成会话失效时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

答案对象固定字段：question_key、option_key、score_snapshot。score_snapshot 只由服务端在最终完成事务中写入，客户端提交时不得携带或覆盖。未完成会话的答案只保留在客户端内存，不写入服务端、历史、后台或审计；最终普通结果是否向本人展示答案，仍按结果投影规则处理。

### 3.10 assessment_results：自测结果快照

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 结果 ID |
| session_id | string | 是 | assessment_sessions ID |
| user_id | string | 是 | 学生账户 ID |
| module_code | string | 是 | phq9、gad7、sleep_observation |
| scoring_rule_version | string | 是 | 计算规则版本 |
| answers_snapshot | array[object] | 否 | ordinary 或 higher_score 结果的完成时答案快照；safety_support 不保存完整答案 |
| fixed_summary | string | 是 | 固定规则生成的结果总结 |
| reference_band | string | 否 | PHQ-9 或 GAD-7 的参考分层；睡眠和 safety_support 为空 |
| boundary_notice | string | 是 | 非诊断和自我观察边界说明 |
| ai_assist_snapshot_id | string | 否 | 可选 AI 辅助快照 ID；安全支持状态为空 |
| result_state | string | 是 | ordinary、higher_score、safety_support |
| score | integer | 否 | ordinary 或 higher_score 的 PHQ-9/GAD-7 分数；睡眠和 safety_support 为空 |
| dimension_summary | object | 是 | 睡眠三维观察或允许的分项摘要 |
| safety_state | string | 是 | not_triggered、can_be_safe、uncertain、cannot_be_safe |
| visible_copy_version | string | 是 | 结果文案版本 |
| deleted_at | datetime | 否 | 单条删除时间 |
| created_at | datetime | 是 | 结果生成时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

唯一约束：session_id。PHQ-9 第 9 题非零且用户尚未完成安全确认时，不创建任何 assessment_results 文档；用户选择 uncertain、完成支持资源确认、主动继续并完成剩余问卷后，才可创建不含完整答案的 safety_support 受限快照；用户选择 cannot_be_safe 时不创建结果。

### 3.10.1 ai_assist_snapshots：AI 辅助快照

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 快照 ID |
| task_type | string | 是 | assessment_explanation、treehole_review_assist |
| resource_type | string | 是 | assessment_result、treehole_post、treehole_response |
| resource_id | string | 是 | 对应结果或社区对象 ID |
| owner_user_id | string | 否 | 学生结果对应的内部账户 ID；不返回模型 |
| input_digest | hash_string | 是 | 脱敏输入摘要，不保存原始输入 |
| request_model | string | 是 | deepseek-v4-flash |
| resolved_model_version | string | 是 | DeepSeek-V4-Flash-0731 |
| prompt_version | string | 是 | xinyu-v2-system-v1 |
| output_status | string | 是 | adopted、fallback、rejected |
| output_projection | object | 否 | 经过结构和策略校验的允许字段 |
| adopted_copy | string | 否 | 被产品采用的辅助文字；fallback 时为空 |
| created_at | datetime | 是 | 生成时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 版本 |

该集合不保存完整模型请求、完整模型响应、姓名、学号、完整答案、原始安全确认或未脱敏正文。safety_support 结果不创建 AI 辅助快照。

### 3.11 support_resources：支持资源

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 资源 ID |
| environment_scope | string | 是 | demo、authorized |
| category | string | 是 | trusted_person、campus、emergency |
| title | string | 是 | 资源名称 |
| description | string | 是 | 资源说明 |
| action_type | string | 是 | call、copy、open_url、text_only |
| action_target | string | 否 | 电话、链接或复制文本；敏感值按配置保护 |
| availability_text | string | 否 | 服务时间 |
| source_text | string | 是 | 来源或维护方 |
| verified_at | datetime | 是 | 最近核验时间 |
| enabled | boolean | 是 | 是否展示 |
| sort_order | integer | 是 | 展示顺序 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 资源版本 |

资源为空或过期时，接口返回配置状态，不生成虚构电话、联系人或链接。

### 3.12 quote_entries：每日短句库

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 短句 ID |
| quote_text | string | 是 | 短句正文 |
| author_text | string | 是 | 作者或来源名称 |
| work_text | string | 否 | 作品名 |
| source_kind | string | 是 | public_domain、project_original、copyright_pending |
| rights_note | string | 是 | 来源和使用备注 |
| enabled | boolean | 是 | 是否可展示 |
| display_from | string | 否 | 生效日期 |
| display_until | string | 否 | 失效日期 |
| sort_order | integer | 是 | 静态轮换顺序 |
| library_version | string | 是 | 短句库版本 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 版本 |

当前启用库为 40 条：30 条公版古典名句和 10 条心语 V2 原创温和短句。动漫台词候选保持 copyright_pending 和 disabled，未完成授权及正式译文核对前不得展示。接口不支持运行时联网抓取或模型生成。

### 3.13 treehole_posts：树洞帖子

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 帖子 ID |
| author_user_id | string | 是 | 作者账户 ID，公开接口不返回 |
| anonymous_identity_id | string | 是 | 发布时匿名身份 ID |
| display_name_snapshot | string | 是 | 当时允许展示的匿名名 |
| body_original_ciphertext | encrypted_string | 否 | 仅检查期间临时保存的原始正文 |
| body_sanitized | string | 否 | 通过规则和人工处理后的展示正文 |
| body_hash | hash_string | 是 | 正文去重和审计摘要 |
| visibility_state | string | 是 | checking、published、protected、pending_confirmation、unpublished、safety_priority、deleted |
| review_state | string | 是 | not_started、automated_checked、human_required、decided |
| safety_state | string | 是 | not_triggered、needs_support_review、handled |
| community_consent_version | string | 是 | 发布时有效的社区同意版本 |
| original_retention_deadline | datetime | 否 | 原始正文清理截止时间 |
| deleted_at | datetime | 否 | 删除时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

原始正文必须加密、禁止发送给 AI 和普通后台接口；最终决定后按 original_retention_deadline 清理。公开列表只读取 body_sanitized。四种最终人工动作固定为公开、保护展示、暂不公开、转安全复核。

### 3.14 treehole_responses：树洞回应

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 回应 ID |
| post_id | string | 是 | treehole_posts ID |
| author_user_id | string | 是 | 回应者账户 ID，公开接口不返回 |
| anonymous_identity_id | string | 是 | 回应时匿名身份 ID |
| display_name_snapshot | string | 是 | 匿名名快照 |
| body_original_ciphertext | encrypted_string | 否 | 检查期间临时原文 |
| body_sanitized | string | 否 | 允许展示的回应文本 |
| state | string | 是 | checking、published、unpublished、deleted |
| community_consent_version | string | 是 | 回应时有效的社区同意版本 |
| deleted_at | datetime | 否 | 删除时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

回应必须同时校验作者社区同意和帖子当前是否接受回应。帖子未公开或安全优先时不得创建公开回应。

### 3.14.1 work_tasks：后台统一任务索引

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 全局任务 ID，必须与一个任务详情集合的 _id 相同 |
| task_kind | string | 是 | content_review、safety_support、identity_access、followup |
| source_type | string | 是 | post、response、assessment_result、identity_request、support_task |
| source_id | string | 是 | 来源对象 ID |
| available_capability | string | 是 | content_review、safety_support、identity_access、followup |
| state | string | 是 | needs_action、claimed、waiting_other、completed、cancelled |
| assigned_admin_id | string | 否 | 当前认领人 |
| safe_summary | string | 是 | W-02 可见的非敏感摘要 |
| object_version | integer | 是 | 当前来源对象版本 |
| last_action | string | 否 | 最近一次动作枚举 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 任务索引版本 |

W-02 只查询本集合。content_review_tasks、safety_support_tasks 和 identity_access_requests 保存对应的专用事实；跟进任务使用本集合的 task_kind 为 followup，并把已发生事实保存到 followup_records。不能通过 W-02 的统一索引绕过专用投影读取完整内容。

### 3.15 content_review_tasks：内容审核任务

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 任务 ID |
| task_kind | string | 是 | content_review |
| post_id | string | 是 | 帖子 ID |
| response_id | string | 否 | 回应 ID，若任务针对回应 |
| state | string | 是 | needs_action、claimed、waiting_other、completed、cancelled |
| assigned_admin_id | string | 否 | 当前认领人 |
| object_version_snapshot | integer | 是 | 创建任务时对象版本 |
| decision | string | 否 | publish、protect、unpublish、safety_review |
| internal_reason | string | 否 | 内部事实性理由，不给学生 |
| automated_check_summary | object | 否 | 固定规则结果摘要，不是 AI 风险判断 |
| completed_at | datetime | 否 | 完成时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 任务版本 |

### 3.16 safety_support_tasks：安全支持任务

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 任务 ID |
| task_kind | string | 是 | safety_support |
| user_reference_id | string | 是 | 学生内部引用，不是姓名学号 |
| source_result_id | string | 是 | 受限结果 ID |
| safety_fact | string | 是 | uncertain、cannot_be_safe |
| support_resource_snapshot | array[object] | 是 | 已向用户展示的资源版本 |
| state | string | 是 | needs_action、claimed、waiting_other、completed |
| assigned_admin_id | string | 否 | 当前认领人 |
| followup_due_at | datetime | 否 | 必要的下一次跟进时间 |
| fact_note | string | 否 | 事实性支持记录，不得写诊断标签 |
| completed_at | datetime | 否 | 完成时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 任务版本 |

演示环境和明确授权环境才允许创建此集合的任务。默认不关联 identity_records，不显示完整答案、完整历史或安全确认原文。

### 3.17 identity_access_requests：身份授权申请

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 申请 ID |
| task_kind | string | 是 | identity_access |
| user_reference_id | string | 是 | 学生内部引用 |
| requester_admin_id | string | 是 | 申请人后台账号 ID |
| requested_fields | array[string] | 是 | 只允许 student_name、student_number 等固定枚举 |
| reason_fact | string | 是 | 事实性申请原因 |
| state | string | 是 | pending、approved、denied、expired、revoked |
| decided_admin_id | string | 否 | 决定人 |
| decision_reason | string | 否 | 内部理由 |
| valid_from | datetime | 否 | 授权起始时间 |
| valid_until | datetime | 否 | 授权结束时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 乐观锁版本 |

身份字段只有在 approved、当前时间位于有效期内且请求字段在允许范围内时才可读取；每次读取写入审计。

### 3.18 followup_records：跟进事实

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 跟进记录 ID |
| task_id | string | 是 | safety_support 或 followup 任务 ID |
| actor_admin_id | string | 是 | 记录人 |
| action_code | string | 是 | resource_provided、contact_made、contact_failed、next_contact_agreed |
| fact_note | string | 是 | 已发生事实，禁止诊断和推断 |
| next_due_at | datetime | 否 | 下一次跟进时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 版本 |

### 3.19 admin_accounts：后台账号

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 后台账号 ID |
| login_name | string | 是 | 固定登录名，由服务端配置匹配 |
| display_name | string | 是 | 心理健康中心工作人员 |
| capability_label | string | 是 | 超级管理员 |
| status | string | 是 | active、disabled |
| password_hash_reference | string | 是 | 密码哈希的配置引用，不保存明文密码 |
| last_login_at | datetime | 否 | 最近登录时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 版本 |

后台不提供角色选择或切换。真实环境可以接入学校账号系统，但页面能力仍必须由服务端 capability 决定。

### 3.20 audit_events：审计事件

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 审计 ID |
| request_id | string | 是 | 请求编号 |
| environment_id | string | 是 | 当前 CloudBase 环境 ID 的非秘密引用 |
| actor_type | string | 是 | student、admin、system |
| actor_id | string | 否 | 操作者内部 ID |
| actor_capability | string | 否 | 当时的后台能力 |
| action | string | 是 | 固定动作枚举 |
| resource_type | string | 是 | user、mood、assessment、post、task、identity、config、demo |
| resource_id | string | 是 | 内部资源 ID |
| data_scope | array[string] | 是 | 读取或变化的最小字段范围 |
| outcome | string | 是 | success、denied、conflict、failure |
| reason_code | string | 否 | 稳定原因码 |
| occurred_at | datetime | 是 | 发生时间 |
| created_at | datetime | 是 | 写入时间 |
| updated_at | datetime | 是 | 固定不更新 |
| version | integer | 是 | 固定为 1 |

审计只读、不允许前端删除或修改，不复制完整正文、完整答案、姓名、学号或安全确认原文。

### 3.21 idempotency_records：幂等记录

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 幂等记录 ID |
| actor_type | string | 是 | student、admin |
| actor_id | string | 是 | 操作者 ID |
| route_key | string | 是 | 规范化接口路径和方法 |
| idempotency_key | string | 是 | 客户端提供的幂等键 |
| request_hash | hash_string | 是 | 请求体摘要 |
| outcome | string | 是 | processing、success、failure |
| response_digest | hash_string | 否 | 成功响应摘要 |
| expires_at | datetime | 是 | 幂等记录有效期 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 版本 |

同一操作者、路径和幂等键如果请求体摘要不同，返回 409，不执行第二次动作。

### 3.22 demo_reset_runs：演示重置记录

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| _id | string | 是 | 重置记录 ID |
| environment_id | string | 是 | 演示环境 ID |
| requested_by_admin_id | string | 是 | 请求人 |
| state | string | 是 | started、completed、partial_failure、failed、rejected |
| affected_collections | array[string] | 是 | 允许重置的集合白名单 |
| collection_results | object | 否 | 每个集合的结果和数量 |
| request_id | string | 是 | 请求编号 |
| started_at | datetime | 是 | 开始时间 |
| completed_at | datetime | 否 | 结束时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| version | integer | 是 | 版本 |

## 4. 索引和唯一约束

必须建立以下索引：

| 集合 | 索引 |
| --- | --- |
| user_accounts | auth_subject_hash 唯一；status、updated_at |
| auth_sessions | access_token_hash 唯一；subject_id、status；access_expires_at |
| consent_records | user_id、consent_kind、occurred_at |
| daily_mood_records | user_id、record_date 唯一；user_id、record_date、deleted_at |
| assessment_sessions | user_id、created_at；user_id、state |
| assessment_results | user_id、module_code、created_at；session_id 唯一 |
| ai_assist_snapshots | resource_type、resource_id、created_at；owner_user_id、created_at |
| treehole_posts | visibility_state、created_at；author_user_id、created_at |
| treehole_responses | post_id、state、created_at；author_user_id、created_at |
| work_tasks | state、updated_at；available_capability、state；assigned_admin_id、state |
| content_review_tasks | state、created_at；assigned_admin_id、state |
| safety_support_tasks | state、created_at；assigned_admin_id、state |
| identity_access_requests | user_reference_id、state；valid_until |
| audit_events | occurred_at；resource_type、resource_id、occurred_at；actor_id、occurred_at |
| idempotency_records | actor_id、route_key、idempotency_key 唯一 |

## 5. API 通用契约

### 5.1 请求头

- Authorization：Bearer 访问令牌，除健康检查和微信换会话外必填。
- X-Request-Id：客户端可提供合法请求编号；没有时由服务端生成。
- Idempotency-Key：所有创建、完成、删除、状态决定和重置请求必填。
- Content-Type：application/json。

服务端不得信任客户端传入的 user_id、admin_id、role、score、visibility_state、safety_state、capability 或 environment_id。

### 5.2 成功响应

~~~json
{
  "request_id": "req_01",
  "data": {},
  "error": null
}
~~~

### 5.3 失败响应

~~~json
{
  "request_id": "req_01",
  "data": null,
  "error": {
    "code": "STABLE_ERROR_CODE",
    "message": "用户可以理解的中文说明",
    "retryable": false,
    "current_version": null
  }
}
~~~

错误消息不得包含堆栈、数据库语句、密钥、其他用户数据或未脱敏文本。

### 5.4 通用错误码

| HTTP 状态 | 错误码 | 含义 |
| --- | --- | --- |
| 400 | INVALID_REQUEST | 字段缺失、格式错误或枚举非法 |
| 401 | AUTH_REQUIRED | 没有有效会话 |
| 401 | SESSION_EXPIRED | 会话过期，需要重新登录或刷新 |
| 403 | CONSENT_REQUIRED | 缺少基础或社区同意 |
| 403 | IDENTITY_REQUIRED | 需要完成身份核验 |
| 403 | FORBIDDEN | 当前主体没有该能力 |
| 404 | NOT_FOUND | 资源不存在或对当前主体不可见 |
| 409 | VERSION_CONFLICT | 对象已被其他请求改变 |
| 409 | IDEMPOTENCY_CONFLICT | 相同幂等键对应不同请求 |
| 422 | VALIDATION_FAILED | 题目答案或业务字段不符合规则 |
| 422 | SAFETY_CONFIRMATION_REQUIRED | PHQ-9 第 9 题非零但尚未完成安全确认 |
| 422 | SAFETY_SUPPORT_BLOCKED | 当前安全分支不允许生成完整结果 |
| 429 | RATE_LIMITED | 请求过频 |
| 500 | INTERNAL_ERROR | 服务端内部失败，用户可重试 |
| 503 | DEPENDENCY_UNAVAILABLE | 微信、身份服务、资源或 AI 依赖不可用 |

## 6. 学生端 API 端点

### 6.1 健康和会话

#### GET /api/v1/health

无需认证。返回服务版本、环境类型和依赖状态摘要，不返回密钥、数据库连接串或真实环境 ID。

响应 data：service 为 string、version 为 string、environment_kind 为 demo 或 authorized、status 为 ok 或 degraded。

#### POST /api/v1/auth/wechat/session

请求：code 为 string，必填；client_version 为 string，必填。

服务端使用 WECHAT_APPID 和 WECHAT_APPSECRET 交换微信凭证，按主体摘要查找或创建学生账户。第一次建立会话不会自动写入基础服务同意。

响应 data：access_token、refresh_token、access_expires_at、refresh_expires_at、account_status、base_consent_status、community_consent_status、identity_status。

#### POST /api/v1/auth/refresh

请求：refresh_token 为 string。服务端校验轮换令牌，撤销旧刷新令牌并返回新的一对令牌。

#### POST /api/v1/auth/logout

请求：无业务字段。撤销当前会话，返回 success 为 true。重复退出视为成功。

### 6.2 初始化和同意

#### GET /api/v1/app/bootstrap

需要有效学生会话。基础同意已完成时返回完整初始化投影；基础同意未完成时只返回非敏感的首次使用配置，不返回私密记录或社区作者内容。

响应 data：account_status、base_consent、community_consent、identity_status、anonymous_identity_summary、today_summary、module_summaries、feature_flags。today_summary 只含启用短句和今日心情摘要，不含完整历史。

#### POST /api/v1/consents/base

请求：document_version 为 string、action 固定为 accepted。

服务端记录 consent_records，并更新 user_accounts 的基础同意。没有基础同意时拒绝需要账户的数据接口。

#### POST /api/v1/consents/community

请求：document_version 为 string、action 固定为 accepted 或 withdrawn。

accepted 恢复发布和回应能力；withdrawn 允许浏览公开树洞，但立即禁止发帖和回应，已有帖子不自动删除。

### 6.3 账户和身份

#### GET /api/v1/me

返回 account_status、同意状态、identity_status、anonymous_identity_summary 和可用功能摘要。绝不返回姓名、学号或后台任务。

#### POST /api/v1/identity/verifications

请求：student_name 为 string、student_number 为 string、client_request_key 为 string。只在 HTTPS 请求体传输，服务端不记录原文日志。

响应：verification_id、status、next_poll_after_seconds。核验成功返回 verified；不可用返回 unavailable；不匹配返回 failed，不泄露正确值。

#### GET /api/v1/identity/verifications/{verification_id}

只返回当前用户自己的 pending、verified、failed 或 unavailable 状态。核验成功不会返回姓名学号。

#### GET /api/v1/me/anonymous-identity

返回 display_name、display_scope 固定为 treehole_only、generation_version 和 status。

### 6.4 今日和心情

#### GET /api/v1/today

需要有效学生会话、基础服务同意和 verified 身份状态；身份未完成时只允许回到身份核验流程。

返回 quote、mood_today、assessment_shortcuts、support_entry。quote 只返回 quote_text、author_text、work_text 和 library_version。

#### PUT /api/v1/moods/today

请求：record_date 为用户本地当天日期、mood_code 为固定枚举、object_version 为 integer、idempotency_key 在请求头。

服务端校验日期只能是当天；同一用户同一天只能首次保存一条记录，重复请求返回已有记录事实，不覆盖当天已经保存的选择。响应返回 record_id、record_date、mood_code、saved_at 和 version。

#### GET /api/v1/moods

查询：from_date、to_date、cursor、limit。只返回当前用户未删除记录的 record_date、mood_code、created_at、updated_at、version。

#### DELETE /api/v1/moods/{record_id}

请求：object_version。只允许本人逐条删除；返回 deleted_at 和 record_id，不支持批量或一键清空。

### 6.5 自测会话和结果

#### GET /api/v1/assessment-modules

需要有效学生会话、基础服务同意和 verified 身份状态。

返回三个固定模块的 module_code、title、description、expected_minutes、current_questionnaire_version、enabled 和最近记录摘要。

#### POST /api/v1/assessment-sessions

请求：module_code、client_start_key。服务端读取当前启用题卷并冻结 questionnaire_version。

响应：session_id、module_code、questionnaire_version、questions、state、expires_at。questions 只包含题目、选项标签和顺序，不包含服务端计分规则。


#### POST /api/v1/assessment-sessions/{session_id}/complete

请求：answers 为 array[object]，每项只有 question_key 和 option_key；object_version。客户端不得提交分数、结果状态或安全状态。服务端在内存中校验题目版本、题目顺序、答案枚举和用户归属。

普通模块全部答案校验通过后，服务端在同一完成事务中写入答案快照、固定结果和结果版本；未完成会话不保存答案。PHQ-9 第 9 题非零时，服务端只记录触发了安全确认这一最小事实，不保存答案；安全确认通过后由客户端继续在内存中保留答案，最终完成时再次提交。

响应 data：completion_state 为 result_ready、safety_confirmation_required 或 safety_support_blocked；session_id、result_id（仅在已经生成结果时）和 safety_triggered。

如果最终提交的 PHQ-9 第 9 题为零，服务端清除旧的安全触发临时状态并按普通或较高分数规则完成；如果最终提交为非零且会话没有 can_be_safe 或 uncertain 确认，返回 422 SAFETY_CONFIRMATION_REQUIRED，不生成结果；如果状态为 cannot_be_safe，返回 safety_support_blocked，不生成结果。

#### POST /api/v1/assessment-sessions/{session_id}/support-resource-ack

请求：resource_context 固定为 safety；resource_version 为 string；object_version。服务端记录当前安全资源已经展示给用户的版本和时间，不保存用户的安全判断。

响应：resource_version、acknowledged_at 和 version。安全确认选择 uncertain 后，用户必须先完成该接口，再主动继续答题；最终 complete 请求必须存在同一会话的资源确认记录。can_be_safe 不要求该记录；cannot_be_safe 直接进入支持资源流程。

#### POST /api/v1/assessment-sessions/{session_id}/safety-confirmation

请求：state 只能是 can_be_safe、uncertain、cannot_be_safe；answers 为截至 PHQ-9 第 9 题的部分 array[object]；object_version。answers 只在本次请求内校验，不在安全确认完成前持久化。

该接口只允许 PHQ-9 会话在第 9 题实际为非零时调用；其他模块、缺少第 9 题或第 9 题为零时返回 VALIDATION_FAILED。

服务端按固定规则执行：can_be_safe 记录确认并返回 continue_assessment，客户端返回答题页；uncertain 记录确认并返回 show_support_resources，完成资源确认后用户主动返回答题页；cannot_be_safe 将会话标记为 abandoned，不保存完整答案、不生成可读完整结果，并仅在演示或明确授权环境创建最小安全任务。

响应：next_step 只能是 continue_assessment、show_support_resources 或 support_only；result_id 固定为 null；support_required、task_created 和 visible_projection 按当前分支返回。visible_projection 只返回当前分支允许的最小字段。

#### POST /api/v1/assessment-sessions/{session_id}/abandon

放弃操作只作用于没有最终结果的会话。in_progress、未完成安全确认和 expired 会话均不保存完整答案。

请求：object_version。标记未完成，不创建结果，重复放弃返回当前状态。

#### GET /api/v1/assessment-results/{result_id}

只允许本人访问。ordinary 和 higher_score 返回固定分数或观察摘要、fixed_summary、reference_band、boundary_notice、支持入口和可选 ai_assist 投影；safety_support 只返回安全分支允许的受限投影，ai_assist 必须为 null。

#### GET /api/v1/assessment-results

查询：module_code、from_date、to_date、cursor、limit。返回本人的结果摘要；不会返回其他用户、后台任务或 AI 运行记录。

#### DELETE /api/v1/assessment-results/{result_id}

只允许本人逐条删除。删除结果不重新计算其他结果，不删除审计必要事实。

### 6.6 支持资源

#### GET /api/v1/support-resources

查询：context 为 normal 或 safety。返回当前环境启用、未过期资源的 title、description、action_type、action_target、availability_text、source_text、verified_at 和 version。

接口不接受用户传入的任意电话或链接，不在资源缺失时生成内容。

### 6.7 树洞

#### GET /api/v1/treehole/posts

查询：sort 只能是 latest 或 confirmed；cursor、limit。只返回 published 或 protected 的 body_sanitized、display_name_snapshot、状态、时间和允许展示的回应数量。

#### POST /api/v1/treehole/posts

前置：基础同意、社区同意、必要身份核验和账户 active。

请求：body 为 string、client_idempotency_key 为 string。服务端保存临时加密原文，执行固定规则检查，创建帖子和必要的 content_review_tasks。

响应：post_id、visibility_state、review_state、display_projection。checking、pending_confirmation、unpublished、safety_priority 时不返回给公共列表的正文。

#### GET /api/v1/treehole/posts/{post_id}

公开状态只返回公开投影；作者访问自己的非公开帖子时返回状态和允许的摘要，不返回内部理由、完整审核备注或其他人的身份。

#### GET /api/v1/me/treehole/posts

返回当前用户作为作者的帖子摘要、状态、创建时间和允许的正文摘要。列表可以包含 checking、published、protected、pending_confirmation、unpublished、safety_priority、deleted。

#### POST /api/v1/treehole/posts/{post_id}/withdraw

只允许作者在状态允许时撤回。请求带 object_version；服务端校验作者、社区状态和当前版本。

#### DELETE /api/v1/treehole/posts/{post_id}

只允许作者逐条删除；请求带 object_version。删除后公开接口不再返回正文，审计保留必要的对象引用和结果。

#### POST /api/v1/treehole/posts/{post_id}/responses

前置：作者社区同意有效、帖子为 published 或 protected 且接受回应。请求：body 为 string、object_version、client_idempotency_key。回应经过同一固定检查流程，不保证立即公开。

#### DELETE /api/v1/treehole/responses/{response_id}

只允许回应作者逐条删除，服务端校验回应状态和对象版本。

## 7. 账户停止使用和恢复 API

### POST /api/v1/account/stop

请求：confirmation_text 为固定确认词、object_version。服务端将账户设为 recovery_pending，计算 recovery_deadline_at 为当前时间加 30 天，并拒绝新观察、发帖和回应。

### POST /api/v1/account/recover

只允许 recovery_pending 状态的本人在截止时间前恢复。成功后恢复 active，但不恢复已经删除的数据和已经结束的内容审核决定。

### GET /api/v1/account/status

返回 status、recovery_deadline_at、可用功能和是否可以恢复。stopped 或 purged 状态不返回私密历史正文。

## 8. 后台认证和 API

### 8.1 后台认证

#### POST /api/v1/admin/auth/login

请求：login_name、password。服务端匹配当前环境配置的固定账号，页面显示名称固定为心理健康中心工作人员，能力固定为超级管理员，不接受客户端 role。

响应：access_token、refresh_token、access_expires_at、refresh_expires_at、display_name、capability_label。

错误时统一返回 AUTH_REQUIRED 或 FORBIDDEN，不透露账号是否存在、密码是否正确或后台数据库状态。

#### POST /api/v1/admin/auth/refresh

按后台会话规则轮换刷新令牌。

#### POST /api/v1/admin/auth/logout

撤销当前后台会话。

#### GET /api/v1/admin/me

返回 display_name、capability_label、session_expires_at 和 environment_kind，不返回密码哈希或内部密钥。

### 8.2 工作台

#### GET /api/v1/admin/workbench

查询：section 只能是 needs_action、waiting_other、recent、all；cursor、limit。返回三个区块的任务摘要。

任务摘要字段固定为 task_id、task_kind、state、created_at、updated_at、assigned_admin_display、safe_summary、object_version。不得返回完整正文、完整答案或身份字段。

#### GET /api/v1/admin/tasks/{task_id}

返回任务详情的最小必要事实、脱敏内容、当前对象版本、允许动作和已发生的事实性处理记录。内容审核、安全支持、身份授权和跟进分别返回对应字段投影。

#### POST /api/v1/admin/tasks/{task_id}/claim

请求：object_version。只有 needs_action 状态可以认领；成功后 state 为 claimed，assigned_admin_id 为当前账号。

#### POST /api/v1/admin/tasks/{task_id}/release

请求：object_version。只有当前认领人可以释放；成功后回到 needs_action 或 waiting_other。

#### POST /api/v1/admin/tasks/{task_id}/decision

内容审核请求字段：action 只能是 publish、protect、unpublish、safety_review；object_version；internal_reason 为事实性说明。

安全支持请求字段：action 只能是 record_support、set_followup、complete；object_version；fact_note；followup_due_at 可选。

身份授权请求字段：action 只能是 approve、deny、revoke；object_version；requested_fields、valid_until 只从服务端申请中读取，不接受客户端扩展。

跟进请求字段：action 只能是 record_followup、complete；object_version；action_code；fact_note；next_due_at 可选。

服务端按 task_kind 选择字段模型，不能用一个任务类型的字段处理另一种任务。成功响应返回 task_id、new_state、new_object_version、audit_request_id。版本冲突返回 409 并返回允许显示的当前状态摘要，不返回受限新增字段。

### 8.3 身份读取

#### POST /api/v1/admin/identity-access-requests

创建身份授权申请。请求包含 user_reference_id、requested_fields 和 reason_fact。申请创建后进入等待或需要处理状态，不立即返回身份字段。

#### GET /api/v1/admin/identity-access-requests/{request_id}

返回申请状态、范围、有效期和事实性理由。只有 approved 且当前有效时才可以进行限定字段读取。

#### GET /api/v1/admin/identity-access-requests/{request_id}/identity

服务端再次校验当前账号能力、授权状态、字段范围和有效期，然后只返回被批准的 student_name 或 student_number。每次成功或拒绝读取都写入 audit_events；读取结果不写入浏览器持久化存储。

### 8.4 审计和演示

#### GET /api/v1/admin/audit-events

查询：from、to、resource_type、action、outcome、cursor、limit。返回 request_id、actor、resource、data_scope、outcome、reason_code、occurred_at。接口只读，不提供编辑和删除。

#### POST /api/v1/admin/demo/reset

仅 DEMO_MODE 为 true 且 CloudBase 环境 ID 命中演示白名单时可用。请求：confirmation_text 固定确认词、reset_scope 为固定集合白名单。

服务端在执行前创建 demo_reset_runs，重置只允许演示账户、演示帖子、演示任务和演示审计相关数据；真实环境直接返回 403 且不开始删除。响应逐集合返回 completed、failed 或 skipped，部分失败不能包装为整体成功。

## 9. 后端认证、授权和数据处理逻辑

### 9.1 学生认证顺序

1. 接收微信一次性登录凭证。
2. 服务端调用微信接口交换主体信息。
3. 对主体生成不可逆摘要，查找或创建 user_accounts。
4. 创建短期访问令牌和轮换刷新令牌，只保存令牌摘要。
5. 在每个业务请求中从令牌恢复 user_id，不接受请求体中的 user_id。
6. 校验账户状态、基础同意、社区同意、身份状态和对象作者关系。

### 9.2 后台认证顺序

1. 接收登录名和密码。
2. 从当前环境读取固定账号配置和密码哈希。
3. 创建 subject_type 为 admin 的会话。
4. 每次任务操作从服务端会话读取 capability，不信任前端显示的角色。
5. 每次受限字段读取校验任务、授权范围、有效期和环境。

### 9.3 权限矩阵

| 能力 | 学生本人 | 普通学生 | 后台默认 | AI |
| --- | --- | --- | --- | --- |
| 读取本人心情 | 是 | 否 | 默认否 | 否 |
| 修改本人心情 | 是 | 否 | 默认否 | 否 |
| 读取本人结果 | 是 | 否 | 任务必要时最小投影 | 否 |
| 浏览公开树洞 | 是 | 是 | 只读必要投影 | 否 |
| 发布和回应 | 社区同意有效时 | 各自同意有效时 | 否 | 否 |
| 内容审核决定 | 否 | 否 | 是，任务范围内 | 否 |
| 安全支持记录 | 否 | 否 | 是，演示或授权任务内 | 否 |
| 读取姓名学号 | 否 | 否 | 仅有效身份授权 | 否 |
| 读取审计 | 否 | 否 | 是，只读 | 否 |
| 重置演示 | 否 | 否 | 是，仅演示环境 | 否 |

### 9.4 AI 适配器逻辑

1. 只有明确的允许任务才可进入 AI 适配器。
2. 适配器先生成字段白名单投影，移除姓名、学号、账户 ID、完整答案、完整安全确认和未脱敏正文。
3. 发送 DeepSeek-V4-Flash-0731 请求，超时 8 秒，失败不自动重试。
4. 校验 JSON Object、字段类型、长度、枚举和禁止词。
5. 固定策略复核失败或请求失败时返回 AI 不可用，由固定文案或人工流程接管。
6. AI 不参与评分、风险判断、诊断、帖子最终公开、安全分支或身份授权。

## 10. 状态迁移

### 10.1 帖子

允许的状态迁移：

- checking → published、protected、pending_confirmation、unpublished、safety_priority；
- pending_confirmation → published、protected、unpublished、safety_priority；
- published → protected、unpublished、deleted；
- protected → published、unpublished、deleted；
- safety_priority → protected、unpublished、deleted；
- unpublished → deleted；
- deleted 不可恢复。

最终人工动作只有 publish、protect、unpublish、safety_review 四种。内部理由不是新的用户状态。

### 10.2 自测

- in_progress → completed、abandoned、expired；
- completed 不回到 in_progress；
- safety_triggered 的 completed 会先经过安全确认或生成受限安全状态；
- deleted 的结果只对本人隐藏，审计仍保留必要事实。

### 10.3 任务

- needs_action → claimed → completed；
- claimed → needs_action；
- claimed → waiting_other；
- waiting_other → needs_action 或 completed；
- completed 和 cancelled 只读。

## 11. 安全、日志和保留

- 所有外部接口必须使用 HTTPS。
- API Key、密码、密文和令牌只在服务端配置或密钥管理中保存。
- 日志只记录 request_id、稳定错误码、耗时和内部资源类型，不记录完整请求体。
- 原始树洞正文和身份密文必须加密，并在用途结束后按 deadline 清理。
- 未完成自测答案不写入 AI、审计正文或前端持久化存储。
- 每次身份字段读取、任务决定、删除、账户停止和演示重置都写审计。
- 审计日志只读；物理保留和清理任务必须保留对象引用、动作、结果和时间。

## 12. Python 服务结构约定

实施时后端目录使用以下职责划分，文件名可以在用户后续开发流程中调整，但职责不得合并到前端：

~~~text
backend/
  app/
    main.py                 HTTP 应用和健康检查
    api/                    路由层，只做输入输出适配
    schemas/                Pydantic 请求和响应模型
    domain/                 状态机、评分和权限规则
    services/               用例服务和事务编排
    repositories/           CloudBase 文档数据库访问适配器
    integrations/           微信、学校核验、DeepSeek 适配器
    security/               令牌、密码、脱敏和授权
    audit/                  审计写入
    config/                 环境配置模型
  scf_bootstrap             CloudBase Python HTTP 启动文件
  requirements.in           直接依赖声明
  requirements.lock        完整锁定依赖
~~~

路由层不直接写数据库，不计算分数，不决定安全分支，不读取密钥。所有业务动作经服务层执行，状态变化和审计写入必须在同一个用例中完成。

## 13. 运行失败处理

- CloudBase 数据库失败：返回 INTERNAL_ERROR 或 DEPENDENCY_UNAVAILABLE，不写成功状态。
- 微信登录失败：返回 AUTH_REQUIRED，不创建半成品账户。
- 学校身份服务失败：返回 DEPENDENCY_UNAVAILABLE，状态为 unavailable。
- DeepSeek 失败：返回固定降级内容，不阻塞评分和安全固定规则。
- 支持资源缺失：返回资源未配置，不生成虚构资源。
- 并发冲突：返回 409 和当前允许显示的事实摘要，客户端改为只读。
- 演示重置部分失败：返回逐集合结果，不伪造全量成功。
