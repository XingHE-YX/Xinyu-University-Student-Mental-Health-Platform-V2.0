# 心语 V2 实施计划文档

## 0. 计划信息

- 文档版本：PLAN-1.0
- 编写日期：2026-08-28
- 计划目标：从当前只有设计文档的项目，构建可在微信开发者工具中验证的学生端、Python 后端和独立桌面 Web 后台
- 计划性质：构建依赖顺序和每一步的完成条件
- 后端主语言：Python 3.11
- 学生端：原生微信小程序
- 管理后台：Vue 3 + TypeScript + Vite 桌面单页应用
- 云环境：CloudBase 演示环境与真实授权环境分离

本计划只定义实现顺序、文件职责、接口落点和完成标准。分支策略、提交策略、子代理安排以及具体测试分层，保留给用户后续提供的开发流程；本文件不预先替用户决定这些流程。

## 1. 目标、架构和技术基线

### 1.1 目标

完成以下可验收产品闭环：

1. 学生可以首次进入、同意基础服务、微信登录并完成必要身份核验。
2. 学生可以使用今日、自测、树洞、我的四个移动端模块。
3. PHQ-9、GAD-7 和睡眠观察可以按固定版本完成、计算、保存和查看。
4. PHQ-9 第 9 题非零时严格进入安全确认和支持资源流程。
5. 树洞发布、检查、公开、保护展示、非公开、安全优先和删除状态完整可追踪。
6. 社区同意撤回后浏览继续可用，发布和回应被阻止，已有内容不自动删除。
7. 后台 W-01 至 W-05 可以在 1440×900 下工作，1280px 为最小工作宽度。
8. 后台支持内容审核、安全支持、身份授权和跟进四种任务变体及 W-04 异常状态。
9. 演示数据可以安全重置，审计日志只读，真实环境不会被重置。
10. DeepSeek 只通过 Python 后端、脱敏输入和固定 JSON 契约提供受限辅助，不能影响评分、安全处置或最终审核决定。

### 1.2 架构

    微信小程序
      → Python 3.11 HTTP 云函数
        → CloudBase 文档型数据库
        → 微信登录、学校身份核验、支持资源配置
        → DeepSeek 受限辅助接口

    桌面浏览器
      → Vue 3 管理后台静态构建产物
        → 同一 Python 业务后端的后台会话和任务接口

### 1.3 全局约束

- AI 不评分、不诊断、不判断风险、不决定帖子状态、不执行安全处置。
- 分数、权限、状态迁移、删除边界、环境隔离和审计都由后端决定。
- 学生端不直连数据库、DeepSeek 或后台高权限接口。
- 姓名、学号、完整答案、完整安全确认、未脱敏正文不进入 AI 请求。
- 安全支持状态优先显示现实资源，不显示不必要的分数、历史、AI 和身份信息。
- 不使用新闻资讯式信息流、游戏化打卡、红黄绿风险色阶和移动端后台。
- 当前没有业务源代码；实施时新增代码必须放在 miniprogram、admin 和 backend 三个明确运行单元中。

## 2. 依赖图和里程碑

实现依赖顺序：

    文档基线
      → 三端工程骨架
        → 后端认证、数据库适配、审计和状态机
          → 学生端接口和页面
          → 管理后台接口和页面
            → AI 受限适配
              → 演示数据、部署和全链路验收

里程碑：

| 里程碑 | 交付结果 |
| --- | --- |
| M0 | 文档、配置位和目录边界确认 |
| M1 | 小程序、后台、Python 函数均可启动，依赖锁定 |
| M2 | 认证、同意、数据库访问、审计和幂等可用 |
| M3 | 今日、自测、结果和安全支持闭环可用 |
| M4 | 树洞和我的数据管理闭环可用 |
| M5 | W-01 至 W-05 后台任务闭环可用 |
| M6 | 演示重置、部署和验收矩阵通过 |

## 3. 阶段 0：文档和配置基线

### 0.1 固定规范入口

检查文件：

- PRD.md
- APP_FLOW.md
- TECH_STACK.md
- FRONTEND_GUIDELINES.md
- BACKEND_STRUCTURE.md
- IMPLEMENTATION_PLAN.md
- docs/v2/V2_CONFIRMED_PRODUCT_DECISIONS.md
- docs/v2/V2_AI_INTERFACE_AND_PROMPT_SPEC.md

动作：确认根目录六份规范与最新 V2 文档中的模块、状态、权限和 Python 后端表述一致。发现差异时先更新规范，再开始代码。

完成条件：产品名称、四个移动端模块、后台五个工作区、Python 3.11、DeepSeek 模型、部署边界和安全分支没有互相矛盾的表述。

### 0.2 创建环境配置登记表

登记表文件：[CONFIGURATION_REGISTRY.md](CONFIGURATION_REGISTRY.md)。

新增或维护的配置记录：

- 微信小程序 AppID；
- 演示 CloudBase 环境 ID；
- 真实授权 CloudBase 环境 ID；
- 学生端和后台 API 地址；
- 后台域名和 HTTPS 来源；
- DeepSeek API Key；
- 学校身份核验服务地址；
- 校内和紧急支持资源；
- 后台账号密码哈希。

完成条件：所有值都有演示、真实、未配置三种明确状态；密钥不进入小程序包、后台构建产物、日志或 Git 跟踪文件。

### 0.3 建立目录边界

计划目录：

~~~text
miniprogram/
  app.json
  app.ts
  app.wxss
  pages/
  components/
  services/
  stores/
  types/
  assets/

admin/
  index.html
  src/
    main.ts
    router/
    stores/
    views/
    components/
    services/
    schemas/
    styles/

backend/
  app/
    main.py
    api/
    schemas/
    domain/
    services/
    repositories/
    integrations/
    security/
    audit/
    config/
  scf_bootstrap
  requirements.in
  requirements.lock
  tests/
~~~

完成条件：学生端、后台和后端没有互相导入运行时实现；共享内容只通过明确的 API 类型或文档复制维护。

## 4. 阶段 1：工程初始化和依赖锁定

### 1.1 初始化学生端工程

文件：miniprogram/app.json、miniprogram/app.ts、miniprogram/app.wxss、miniprogram/project.config.json。

动作：

1. 创建原生微信小程序工程。
2. 注册四个主页面和关键流程页面。
3. 配置底部导航顺序为今日、自测、树洞、我的。
4. 配置演示 API 地址，不写入 DeepSeek 密钥。
5. 建立全局安全区、主题变量和页面生命周期入口。

完成条件：微信开发者工具可以打开、编译并显示四项底部导航的空壳页面；尚未接入数据时明确显示空状态。

### 1.2 安装学生端依赖

锁定：TypeScript 7.0.2、miniprogram-api-typings 5.2.3。学生端不安装第三方 UI、网络请求、图表或 AI 包。

文件：miniprogram/package.json、miniprogram/package-lock.json、miniprogram/tsconfig.json。

完成条件：依赖安装结果可重复，微信开发者工具预览不需要额外运行时包。

### 1.3 初始化后台工程

文件：admin/package.json、admin/vite.config.ts、admin/tsconfig.json、admin/index.html、admin/src/main.ts。

动作：使用 Vue 3 + TypeScript + Vite 创建桌面单页应用，设置 Node.js 22.21.0、npm 10.9.4，安装 TECH_STACK.md 中的精确依赖。

必须提供的脚本：

~~~text
npm run dev
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
~~~

完成条件：后台在本地启动，浏览器能显示桌面提示或后台空壳，不引入移动底部导航。

### 1.4 初始化 Python 后端

文件：backend/pyproject.toml、backend/requirements.in、backend/app/main.py、backend/scf_bootstrap、backend/.python-version。

动作：

1. 本地 Python 使用 3.11.11。
2. 安装 FastAPI 0.128.8、Pydantic 2.13.4、httpx 0.28.1、Uvicorn 0.39.0。
3. scf_bootstrap 启动 FastAPI 应用并监听 0.0.0.0:9000。
4. 增加 GET /api/v1/health。
5. 禁止在导入模块时连接数据库或调用外部 API。

完成条件：本地可以启动健康检查；CloudBase Python 3.11 HTTP 函数打包结构包含启动文件和锁定依赖。

### 1.5 生成完整依赖锁

文件：backend/requirements.lock、admin/package-lock.json、miniprogram/package-lock.json。

动作：在指定版本的 Python 和 Node 环境使用 pip-tools 7.6.1 生成完整锁定结果。传递依赖也必须固定，禁止使用 latest、脱字符号和波浪号范围。

完成条件：清空环境后仍能按 TECH_STACK.md 的命令安装同一依赖集合；版本差异必须回到技术文档记录。

## 5. 阶段 2：后端基础能力

### 2.1 配置和环境识别

文件：backend/app/config/settings.py、backend/app/config/environments.py。

实现：

- Pydantic 配置模型读取环境变量；
- 区分演示和真实授权环境；
- 启动时校验 CloudBase 环境 ID 与 DEMO_MODE 是否一致；
- 缺少支持资源、身份核验或 DeepSeek Key 时返回未配置状态；
- 密钥只进入服务端内存，不在配置接口回传。

完成条件：真实环境不能被 DEMO_MODE=true 伪装为演示环境，演示重置在真实环境启动前就被拒绝。

### 2.2 统一请求、响应和错误

文件：backend/app/schemas/envelope.py、backend/app/schemas/errors.py、backend/app/api/dependencies.py。

实现统一响应：

~~~python
class ApiEnvelope:
    request_id: str
    data: object | None
    error: ApiError | None
~~~

实现：请求编号、用户可读中文错误、稳定错误码、可重试标记和异常映射。内部异常只记录服务端日志摘要，不把堆栈返回客户端。

完成条件：所有 API 都能返回相同结构，400、401、403、404、409、422、429、500 和 503 均有稳定错误码。

### 2.3 会话和认证

文件：backend/app/security/tokens.py、backend/app/integrations/wechat_auth.py、backend/app/api/auth.py、backend/app/api/admin_auth.py。

实现：

1. 学生使用微信一次性凭证换取学生会话。
2. 后台使用固定账号配置和密码哈希登录，页面不提供角色选择。
3. 访问令牌保存摘要，学生访问 15 分钟、刷新 30 天；后台访问 15 分钟、刷新 8 小时。
4. 刷新令牌每次轮换，退出时撤销。
5. 从令牌恢复主体，不信任请求体中的 user_id、admin_id 或 capability。

完成条件：登录、刷新、退出、过期、撤销、主体类型和环境隔离均有测试。

### 2.4 CloudBase 数据访问适配器

文件：backend/app/repositories/cloudbase_gateway.py、backend/app/repositories/*.py。

实现：

- 使用 httpx 封装 CloudBase 文档数据库 HTTP API；
- 业务服务只依赖仓储接口，不直接拼装 CloudBase 请求；
- 所有更新支持 version 条件；
- 数据库错误转换为稳定 API 错误；
- 正式集合、索引和权限规则通过后端部署步骤创建，不由小程序启动时创建。

完成条件：仓储层能执行查询、条件更新、逻辑删除和游标分页；单元测试可替换为内存仓储。

### 2.5 幂等和审计

文件：backend/app/services/idempotency_service.py、backend/app/audit/writer.py、backend/app/repositories/idempotency_repository.py、backend/app/repositories/audit_repository.py。

实现：

- 创建、完成、删除、任务决定、账户停止、重置都要求 Idempotency-Key；
- 同一主体、路径和键的请求体不同返回 409；
- 受限读取和状态变化写 audit_events；
- 审计不保存完整答案、完整正文、姓名、学号或安全确认原文。

完成条件：重复点击不会产生重复帖子、结果、删除、任务决定或重置。

## 6. 阶段 3：后端领域规则和数据

### 3.1 集合、索引和种子数据

文件：backend/app/domain/models.py、backend/app/repositories/collection_registry.py、backend/scripts/seed_demo.py、backend/scripts/create_indexes.py。

动作：按 BACKEND_STRUCTURE.md 创建 user_accounts、auth_sessions、identity_records、consent_records、anonymous_identities、daily_mood_records、assessment_modules、assessment_questionnaires、assessment_sessions、assessment_results、ai_assist_snapshots、support_resources、quote_entries、treehole_posts、treehole_responses、work_tasks、content_review_tasks、safety_support_tasks、identity_access_requests、followup_records、admin_accounts、audit_events、idempotency_records 和 demo_reset_runs。

完成条件：每个集合字段、索引、唯一约束和演示数据与后端结构文档一致；真实环境不执行演示种子脚本。

### 3.2 同意和身份核验

文件：backend/app/services/consent_service.py、backend/app/services/identity_service.py、backend/app/integrations/school_identity.py。

实现：

- 基础服务同意和社区同意分别记录版本；
- 社区同意撤回只禁止发帖和回应，不删除已有帖子；
- 姓名学号只进入加密身份记录；
- 学校核验不可用时返回 unavailable，不伪造 verified；
- 匿名身份生成与真实身份查询分离。

完成条件：同意撤回、重新同意、身份成功、失败、不可用和会话失效都有明确状态。

### 3.3 题卷和固定评分

文件：backend/app/domain/assessment_rules.py、backend/app/services/assessment_service.py、backend/app/schemas/assessment.py、backend/scripts/seed_assessments.py。

实现：

1. 导入 PHQ-9 九题、GAD-7 七题和睡眠观察八题的冻结版本。
2. 开始会话时冻结 questionnaire_version。
3. 未完成会话的答案只保留在客户端内存；完成请求或安全确认请求一次性提交完整答案，服务端在内存校验。
4. 客户端只提交题目和选项，不提交 score、result_state 或 safety_state。
5. PHQ-9 与 GAD-7 使用服务端固定计分。
6. 睡眠观察只生成三维观察摘要，不生成医学总分。
7. 按固定较高分数展示规则生成 ordinary 或 higher_score。

完成条件：答案缺失、非法选项、重复提交、题卷版本变化、结果重复生成都能被正确处理。

### 3.4 安全分支

文件：backend/app/domain/safety_rules.py、backend/app/services/safety_service.py、backend/app/api/assessment.py。

实现：

- PHQ-9 第 9 题非零强制进入安全确认；
- uncertain 分支先调用安全资源确认接口，资源版本确认后才允许用户主动继续；
- can_be_safe 继续结果且不创建后台安全任务；
- uncertain 先展示支持资源，演示或明确授权环境创建最小安全任务；
- cannot_be_safe 不返回完整结果，演示或明确授权环境创建最小安全任务；
- 安全状态接口投影不包含不必要分数、历史、AI 和身份信息。

完成条件：无法通过前端跳转、重复提交或改写状态字段绕过安全确认；安全任务只在允许环境创建。

### 3.5 今日、心情、短句和支持资源

文件：backend/app/services/today_service.py、backend/app/services/mood_service.py、backend/app/services/quote_service.py、backend/app/services/support_resource_service.py。

实现：

- 每天返回一条启用短句；
- 当前库启用 30 条公版古典名句和 10 条项目原创句；
- 动漫候选保持禁用状态；
- 心情按用户和日期唯一首次保存，可单条删除；当天再次提交只返回已记录事实，不覆盖已保存选择；
- 支持资源按普通或安全上下文返回，缺失时返回未配置。

完成条件：短句不联网抓取、不由 AI 生成，心情不触发后台任务，资源不会出现虚构电话。

## 7. 阶段 4：学生端业务接口和页面

### 4.1 学生端 API 服务层

文件：miniprogram/services/http.ts、miniprogram/services/auth.ts、miniprogram/services/today.ts、miniprogram/services/assessment.ts、miniprogram/services/treehole.ts、miniprogram/services/me.ts、miniprogram/types/api.ts。

实现：

- 统一添加 Authorization、请求编号和幂等键；
- 统一处理会话失效、版本冲突、未同意、未核验、网络失败；
- 页面不能直接拼接后端 URL 或数据库字段；
- 服务层只返回页面需要的最小投影。

完成条件：页面层不出现 DeepSeek、CloudBase 数据库或后台权限字段。

### 4.2 移动端外壳和全局组件

文件：miniprogram/components/page-container、top-bar、bottom-nav、primary-button、state-message、empty-state、confirm-sheet。

实现顺序：

1. 页面背景、手机左右边距和安全区。
2. 顶部标题栏和返回规则。
3. 四项底部导航。
4. 加载、空、错误和会话失效状态。
5. 按钮、选项、输入和确认弹层。

完成条件：所有后续页面只组合这些基础状态，不各自发明颜色、间距和错误行为。

### 4.3 首次使用和身份核验

文件：miniprogram/pages/onboarding、miniprogram/pages/identity-verification、miniprogram/stores/session.ts。

实现路径：先从今天开始 → 基础服务同意 → 微信登录 → 先确认这是你的记录 → 身份核验 → 生成默认匿名身份 → 今日；后续功能发现身份缺失时进入身份核验并返回原功能。

完成条件：同意、登录、核验成功、失败、不可用、取消和会话过期不产生假成功；姓名学号退出页面后不进入持久化存储。

### 4.4 今日模块

文件：miniprogram/pages/today、miniprogram/components/daily-quote、mood-picker、today-entry。

实现：短句、今日心情、自测快捷入口、支持入口和最近观察摘要；保存心情使用当天幂等首次保存。

完成条件：短句和心情分别失败时页面仍可用；未保存不能显示已保存。

### 4.5 自测中心和答题

文件：miniprogram/pages/assessment-center、miniprogram/pages/assessment-answer、miniprogram/components/question-option、assessment-progress。

实现：

- 三个固定模块；
- 一题一页、固定进度、返回修改；
- 未完成离开提示；
- 本地只在内存保留未提交普通答案；
- 完成按钮幂等；
- 第 9 题非零时立即跳转安全页；可以保证安全返回答题页，不太确定先进入资源页再主动返回答题页，无法保证安全只保留支持资源；
- 最终完成请求一次性提交全部答案，服务端通过固定规则生成结果。

完成条件：三种模块都能完成，任何客户端自带分数或状态字段都会被后端忽略或拒绝。

### 4.6 结果和安全支持

文件：miniprogram/pages/assessment-result、miniprogram/pages/safety-confirmation、miniprogram/pages/support-resources、miniprogram/components/result-summary、support-resource-list。

实现：普通、较高分数、安全支持和数据不足四类投影；安全页三路选择；安全状态不显示多余信息。

完成条件：PHQ-9 第 9 题非零始终先进入安全确认；cannot_be_safe 不显示完整结果；资源缺失不编造联系方式。

### 4.7 历史和逐条删除

文件：miniprogram/pages/history、miniprogram/components/history-item、miniprogram/pages/delete-confirmation。

实现：心情、自测、睡眠三类记录分页；详情和单条删除；无批量删除、一键清空和导出。

完成条件：删除后列表事实正确，版本冲突不覆盖其他设备的最新变化。

### 4.8 树洞模块

文件：miniprogram/pages/treehole、miniprogram/pages/treehole-publish、miniprogram/pages/treehole-detail、miniprogram/pages/my-content、miniprogram/components/treehole-post、content-status。

实现顺序：

1. 公开和保护展示列表；
2. 详情和允许展示回应；
3. 社区同意拦截；
4. 身份核验拦截；
5. 发布、固定规则检查、检查中状态；
6. 撤回、删除和我的内容；
7. 社区同意撤回后的浏览可用、发布和回应禁用。

完成条件：checking、published、protected、pending_confirmation、unpublished、safety_priority、deleted 状态展示准确；非公开状态不泄露正文和内部理由。

### 4.9 我的、隐私和账户停止

文件：miniprogram/pages/my、miniprogram/pages/anonymous-identity、miniprogram/pages/privacy、miniprogram/pages/account-stop。

实现：匿名身份、历史、支持资源、我的内容、同意管理、社区同意撤回、账户停止和 30 天恢复。

完成条件：撤回社区同意不会自动删除已有帖子；停止使用期间不能新增观察、帖子或回应；恢复不恢复已删除数据。

## 8. 阶段 5：后台 Web 工作台

### 5.1 后台外壳和宽度阻断

文件：admin/src/App.vue、admin/src/router/index.ts、admin/src/styles/tokens.css、admin/src/components/AdminShell.vue、DesktopWidthNotice.vue。

实现：

- 标准画布 1440×900；
- 1280px 以上显示后台；
- 低于 1280px 只显示电脑浏览器提示；
- 不出现学生端底部导航；
- 外壳显示固定账号名称、能力和会话状态。

完成条件：1280px、1440px、1920px 和窄屏状态均符合前端指南。

### 5.2 后台登录 W-01

文件：admin/src/views/AdminLoginView.vue、admin/src/services/adminAuth.ts、admin/src/stores/adminSession.ts。

实现：固定账号展示、不提供角色选择、统一登录错误、过期清理详情、退出会话。

完成条件：客户端伪造 role 或 capability 不会扩大服务端权限；登录失败不透露账号存在性。

### 5.3 任务工作台 W-02

文件：admin/src/views/WorkbenchView.vue、admin/src/components/TaskSection.vue、TaskCard.vue、admin/src/services/workbench.ts。

实现三个固定区块：需要我处理、等待他人、最近处理。每个区块独立加载、空状态、错误重试和分页。

完成条件：列表只返回任务摘要和最小事实；某区块失败不覆盖另外两个区块。

### 5.4 任务详情 W-03

文件：admin/src/views/TaskDetailView.vue、admin/src/components/TaskFactsPanel.vue、TaskActionPanel.vue、TaskStateBar.vue。

实现两栏结构：必要事实与脱敏内容、当前操作。根据 content_review、safety_support、identity_access、followup 显示不同字段和动作。

完成条件：无关字段不通过接口返回，也不只是用 CSS 隐藏；操作提交带对象版本和幂等键。

### 5.5 异常状态 W-04

文件：admin/src/components/ConcurrencyState.vue、PermissionState.vue、SessionExpiredState.vue、SubmitFailureState.vue。

实现并发冲突、状态已变化、无权限、会话过期、提交失败、空数据和加载失败。

完成条件：冲突页面转只读；无权限不返回受限字段；提交失败不显示成功；会话过期清除详情。

### 5.6 审计和演示 W-05

文件：admin/src/views/AuditDemoView.vue、admin/src/components/AuditTable.vue、DemoResetDialog.vue、admin/src/services/audit.ts。

实现只读审计筛选、分页、请求编号和演示重置确认。重置前显示环境名和数据范围，服务端逐集合返回结果。

完成条件：真实环境重置请求在服务端被拒绝且不开始删除；审计没有编辑和删除按钮。

## 9. 阶段 6：AI 受限辅助

### 6.1 固定适配器和提示词

文件：backend/app/integrations/deepseek_client.py、backend/app/services/ai_assist_service.py、backend/app/domain/ai_policy.py、backend/app/config/ai_prompt.py。

固定配置：

- 请求地址：https://api.deepseek.com/chat/completions；
- 请求模型：deepseek-v4-flash；
- 解析版本：DeepSeek-V4-Flash-0731；
- 提示词版本：xinyu-v2-system-v1；
- JSON Object；
- temperature 为 0.2；
- 流式关闭；
- 总超时 8 秒；
- 自动重试 0 次；
- API Key 只从服务端 DEEPSEEK_API_KEY 读取。

提示词固定为：模型是心语 V2 的受限文字辅助模块，只能根据 task_type 执行自测固定结果说明或树洞脱敏初筛；不得评分、诊断、判断风险、复原身份、输出思维链或决定安全处置；必须只返回符合契约的 JSON；输入缺失、矛盾、包含安全确认或要求判断风险时返回 needs_fallback。

完成条件：完整提示词和 JSON 结构保存在 docs/v2/V2_AI_INTERFACE_AND_PROMPT_SPEC.md；输入投影、输出校验、策略复核和失败回退都有测试。

### 6.2 AI 与产品状态隔离

实现：

- AI 结果不写入评分字段；
- AI 不改变 fixed_band、safety_state、visibility_state 或 task_state；
- 树洞 AI 失败时进入等待确认或人工处理；
- 自测 AI 失败时继续展示固定规则结果；
- 审计只记任务类型、模型版本、提示词版本和结果类别，不记完整输入输出。

完成条件：关闭 DeepSeek Key 后，自测评分、安全分支和人工审核仍可完成。

## 10. 阶段 7：部署和环境初始化

### 7.1 CloudBase 环境

动作：创建独立演示和真实授权环境，分别配置数据库、索引、函数、静态托管、域名和密钥。

完成条件：环境 ID 不同，演示后台无法读取真实数据，真实环境拒绝演示重置。

### 7.2 Python 云函数

动作：

1. 使用 Python 3.11 构建后端依赖包。
2. 将业务包、scf_bootstrap 和 requirements.lock 对应依赖打包。
3. 在 CloudBase Python HTTP 函数入口创建或上传函数。
4. 配置 9000 端口启动和服务端环境变量。
5. 先访问健康检查，再执行接口契约测试。

微信开发者工具负责小程序项目的预览、真机核验和小程序上传。若当前版本的微信开发者工具不提供 Python 运行时模板，不能把 Python 包伪装成其他运行时函数；按 CloudBase Python 函数上传规范发布后，再回到微信开发者工具验证调用。

完成条件：健康检查成功，错误配置不会泄露密钥，函数日志不出现完整请求体。

### 7.3 学生端部署

动作：

1. 在微信开发者工具填写用户提供的 AppID。
2. 选择演示 CloudBase 环境。
3. 上传小程序代码并进行模拟器、真机和网络失败验证。
4. 记录工具版本、基础库版本和体验版版本号。

完成条件：四项底部导航、关键流程和演示数据均可从微信开发者工具进入；后台 Web 不被打包进小程序。

### 7.4 后台静态托管

动作：

1. 执行后台类型检查、代码检查、测试和构建。
2. 将 admin/dist 发布到对应 CloudBase 环境静态网站托管。
3. 配置 HTTPS、后台来源和 API 地址。
4. 分别验证演示和真实授权入口。

完成条件：1440×900 可工作，低于 1280px 显示电脑提示，刷新路由不泄露受限详情。

## 11. 阶段 8：完成前验收

### 11.1 自动验证

后端：

~~~text
ruff check .
ruff format --check .
mypy .
pytest
~~~

后台：

~~~text
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
~~~

学生端：在微信开发者工具完成编译、页面路径检查和基础库兼容检查。

### 11.2 关键人工路径

1. 首次使用、同意、登录、身份核验成功和失败。
2. 今日短句、心情首次保存成功、保存失败和当天再次进入只读。
3. PHQ-9 普通、较高分数、安全确认三路分支。
4. GAD-7 普通和较高分数结果。
5. 睡眠八题和三维观察结果，不出现医学总分。
6. 树洞发布、检查中、公开、保护展示、未公开、安全优先和删除。
7. 撤回社区同意后的浏览、发帖和回应权限。
8. 我的内容逐条删除和账户停止使用 30 天恢复。
9. 后台三任务区块、四类任务详情和五类 W-04 异常状态。
10. 审计只读、演示重置成功、部分失败和真实环境拒绝。

### 11.3 隐私和安全检查

- 搜索前端构建产物不得出现 DeepSeek API Key、学校密钥或后台密码。
- 检查网络请求不得将完整答案、安全确认、姓名、学号和未脱敏正文发送给 AI。
- 检查学生端和后台不能直连数据库管理接口。
- 检查 API 不能接受客户端伪造 score、role、safety_state、visibility_state 或 environment_id。
- 检查会话过期后敏感详情清除。
- 检查审计只保存最小事实。

### 11.4 设计验收

- 移动端四模块与页面路径和 APP_FLOW.md 一致；
- 颜色、字号、间距、热区、圆角和断点与 FRONTEND_GUIDELINES.md 一致；
- 1440×900 后台结构与 W-01 至 W-05 一致；
- 安全页面不显示不必要分数、历史、AI 和身份；
- 不出现渐变、发光、卡片墙、红黄绿风险色阶或移动端后台。

## 12. 完成定义

只有同时满足以下条件，才可称为 V2 首版实现完成：

1. 三个运行单元可以按技术栈文档启动和部署。
2. 后端结构文档中的集合、接口、状态、权限和审计规则均已实现。
3. APP_FLOW.md 中每条成功和错误路径至少有可复现验证结果。
4. PRD.md 中的非目标没有被代码或配置绕过。
5. 演示环境和真实授权环境物理隔离，演示重置经过实测。
6. Python 后端运行正常，未残留非 Python 的云函数实现或依赖。
7. DeepSeek 不可用时，固定规则和人工流程仍能完成核心功能。
8. 用户提供的开发流程已经用于确定分支、提交、测试分层和协作方式，并且没有被本文件默认替代。
