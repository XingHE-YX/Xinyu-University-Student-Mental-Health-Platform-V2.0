# 心语 V2 开发代理规范

## 0. 文档定位与最高优先级

本文件是心语 V2 项目中供 AI、开发者和自动化工具使用的工作约束。它只规定如何理解项目、如何组织代码、如何引用设计系统以及哪些行为绝对禁止；产品范围、页面流程、接口字段和数据规则仍以本文件末尾列出的规范文档为准。

心语 V2 是面向大学生的心理健康自助观察与匿名轻社区微信小程序，配套一个独立的桌面 Web 管理后台。它不是 App、新闻资讯产品、医疗诊断工具、心理治疗系统或危机处置系统。

规范冲突处理顺序：

1. 根目录六份当前规范：`PRD.md`、`APP_FLOW.md`、`TECH_STACK.md`、`FRONTEND_GUIDELINES.md`、`BACKEND_STRUCTURE.md`、`IMPLEMENTATION_PLAN.md`。
2. `docs/v2/` 中最新的产品确认、技术部署、AI、每日短句和医学依据文档。
3. `docs/superpowers/specs/` 中用于补充页面、状态、权限、后台、演示和验收细节的规格文档。
4. 历史原型、旧说明、视觉预览和聊天记录不能恢复已经被当前标准替代的决策。

如果仍有会影响实现、数据边界或安全行为的真实矛盾，先记录矛盾并请求确认；不得静默选择一个版本。视觉预览目录中的静态、不可点击装饰按钮不自动构成功能需求。

## 1. 每次会话开始的强制读取顺序

每次 AI 会话开始，在检查其他项目文件、提出实现方案或修改任何文件之前，必须：

1. 从项目根目录完整读取 `progress.txt`；如果文件存在但为空，也要确认已读取。
2. 从项目根目录完整读取 `lessons.md`；如果文件存在但为空，也要确认已读取。
3. 完整读取本文件中与当前任务相关的章节。
4. 再读取当前任务涉及的规范文档；不能只看标题、摘要、搜索结果或文档末尾。

`progress.txt` 用于记录项目当前进度和下一项工作入口。`lessons.md` 用于记录真实发生过的错误、原因、修复方式和以后必须遵守的规则。遇到新的可复用错误或边界规则时，应在用户允许的开发流程范围内追加记录，不删除已有经验。

在开发流程、分支方式、提交方式、测试分层、任务拆分或子代理使用方式尚未由用户指定时，不得自行替用户制定这些协作流程。本文件的技术约束不替代用户后续提供的开发流程。

## 2. 项目运行单元与边界

项目由三个相互隔离的运行单元组成：

| 运行单元 | 主要目录 | 技术形态 | 负责内容 |
| --- | --- | --- | --- |
| 学生端 | `miniprogram/` | 原生微信小程序、TypeScript、WXML、WXSS | 今日、自测、树洞、我的 |
| 业务后端 | `backend/` | Python 3.11、FastAPI、CloudBase Python HTTP 云函数 | 认证、规则、数据、权限、审计、AI 调用 |
| 管理后台 | `admin/` | Vue 3、TypeScript、Vite 桌面单页应用 | W-01 至 W-05 工作台 |

学生端底部导航固定为：今日、自测、树洞、我的。后台是独立桌面 Web UI，不进入移动端底部导航，也不压缩为移动端后台。

所有业务数据只能经 Python 业务后端访问。学生端和管理后台不得直连 CloudBase 数据库管理接口；前端不得直接调用 DeepSeek。演示环境与真实授权环境必须使用不同的环境 ID、数据命名空间、函数配置、静态托管配置和密钥。

## 3. 技术栈摘要与固定版本

### 3.1 工具和运行时

| 工具或运行时 | 固定版本或形态 | 规则 |
| --- | --- | --- |
| 微信开发者工具 | `2.01.2510290`（项目参考版本） | 小程序预览、真机核验和上传 |
| Node.js | `22.21.0` | 仅用于管理后台构建工具链，不运行后端 |
| npm | `10.9.4` | 使用锁文件安装依赖 |
| Python | `3.11.11`（本地） | 后端开发与测试；云端使用 Python 3.11 运行时 |
| Git | `2.50.1` | 版本管理；分支和提交流程由用户另行指定 |
| 数据库 | CloudBase 文档型数据库 | 只能由后端仓储适配器访问 |

### 3.2 学生端

- 原生微信小程序：TypeScript、WXML、WXSS。
- `typescript@7.0.2`。
- `miniprogram-api-typings@5.2.3`。
- 只使用微信原生接口和项目内组件；不使用 React、Tailwind、axios、第三方请求封装、第三方登录包、图表库或客户端 AI SDK。

### 3.3 管理后台

- `vue@3.5.42`、`vue-router@5.3.0`、`pinia@4.0.3`、`zod@4.4.3`。
- `vite@8.2.2`、`@vitejs/plugin-vue@6.0.8`、`typescript@7.0.2`、`vue-tsc@3.3.11`。
- `vitest@4.1.11`、`jsdom@30.0.1`、`@testing-library/vue@8.1.0`。
- `eslint@10.9.1`、`eslint-plugin-vue@10.10.0`、`@typescript-eslint/parser@8.68.0`、`@typescript-eslint/eslint-plugin@8.68.0`。
- `eslint-config-prettier@10.1.8`、`prettier@3.9.6`、`@types/node@26.4.0`。
- 不使用 shadcn/ui、Element Plus、Ant Design Vue、Naive UI 或其他大型 UI 组件库；后台组件由项目内 Vue 组件实现。

### 3.4 Python 后端

- 云端运行时：CloudBase Python 3.11 HTTP 云函数。
- 本地 Python：`3.11.11`。
- 运行依赖：`fastapi==0.128.8`、`pydantic==2.13.4`、`httpx==0.28.1`、`uvicorn==0.39.0`。
- 开发依赖：`pytest==8.4.2`、`pytest-asyncio==1.2.0`、`ruff==0.16.5`、`mypy==1.19.1`、`pip-tools==7.6.1`。
- 不使用 ORM；通过 `repositories/` 下的 CloudBase 文档数据库访问适配器调用数据库接口。
- Python 函数包必须包含 `backend/scf_bootstrap`，FastAPI 应用监听 `0.0.0.0:9000`。微信开发者工具负责小程序侧验证和上传；Python 函数按 CloudBase Python 函数规范发布，不伪装为其他运行时。

### 3.5 DeepSeek 受限辅助

| 配置 | 固定值 |
| --- | --- |
| Provider | DeepSeek |
| API Base URL | `https://api.deepseek.com` |
| API Path | `/chat/completions` |
| 请求模型参数 | `deepseek-v4-flash` |
| 记录的解析版本 | `DeepSeek-V4-Flash-0731` |
| API Key | 服务端环境变量 `${DEEPSEEK_API_KEY}`，由用户填写 |
| 提示词版本 | `xinyu-v2-system-v1` |
| 输出 | JSON Object；首版 `stream=false` |
| 温度 | `0.2` |
| 超时 | `8` 秒，包含连接和读取 |
| 自动重试 | `0` 次 |
| 单函数实例并发 | `4` 个请求 |

AI 只允许用于 `assessment_explanation` 和 `treehole_review_assist`。AI 不评分、不修改量表分层、不判断自伤风险、不诊断、不提供治疗方案、不做安全处置、不决定帖子最终状态、不读取真实身份。模型不可用时，固定规则结果和人工流程必须继续工作。

每日短句只能来自项目自建、版本化的短句库。可以人工收集带有激励意义的名人名言、古诗词、动漫台词等，但必须保留出处，展示格式为“短句——作者 / 作品”；项目原创句标注“——心语 V2”。运行时不抓取网络短句，不由 AI 生成短句，不做个性化推荐。

## 4. 文件和目录约定

### 4.1 固定目录边界

实现时遵循以下边界。学生端、后台和后端不得互相导入对方的运行时实现；跨端共享信息只通过明确的 API 契约或文档复制维护。

```text
/
  AGENT.md
  progress.txt
  lessons.md
  PRD.md
  APP_FLOW.md
  TECH_STACK.md
  FRONTEND_GUIDELINES.md
  BACKEND_STRUCTURE.md
  IMPLEMENTATION_PLAN.md

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
```

### 4.2 学生端命名和存放

- 所有页面放在 `miniprogram/pages/`，每个页面使用 kebab-case 目录名，例如 `pages/assessment-center/`、`pages/treehole-detail/`。
- 页面目录内固定使用 `index.ts`、`index.wxml`、`index.wxss`、`index.json`；页面专属辅助文件也只能放在该页面目录内。
- 所有可复用小程序组件放在 `miniprogram/components/`，每个组件使用 kebab-case 目录名，例如 `components/bottom-nav/`、`components/state-message/`。
- 组件目录内固定使用 `index.ts`、`index.wxml`、`index.wxss`、`index.json`。页面专属且不会复用的片段留在页面目录，不放入全局组件目录。
- API 和业务请求适配放在 `miniprogram/services/`，文件名使用 kebab-case 或项目已经锁定的领域名，例如 `assessment.ts`、`treehole.ts`、`me.ts`；页面不得直接拼接请求 URL 或数据库请求。
- 轻量前端状态放在 `miniprogram/stores/`，文件名使用领域名加 `.ts`，例如 `session.ts`。未完成自测答案只保留在当前会话的内存状态，不写入持久化存储或服务端。
- 前端类型放在 `miniprogram/types/`，使用 `.ts`；API 类型必须与 `BACKEND_STRUCTURE.md` 的响应契约同步。
- 图片和静态资源放在 `miniprogram/assets/`；不得把密钥、身份字段、完整答案或后台数据放入资源文件。

### 4.3 管理后台命名和存放

- 所有可复用后台组件放在 `admin/src/components/`，使用 PascalCase 的 Vue 单文件组件，例如 `AdminShell.vue`、`TaskSection.vue`、`TaskFactsPanel.vue`。
- 页面视图放在 `admin/src/views/`，使用 PascalCase，并以 `View.vue` 结尾，例如 `WorkbenchView.vue`、`TaskDetailView.vue`。
- 路由放在 `admin/src/router/`，状态放在 `admin/src/stores/`，服务端请求适配放在 `admin/src/services/`，边界校验模型放在 `admin/src/schemas/`，全局样式令牌放在 `admin/src/styles/`。
- 服务和 store 文件使用 camelCase 领域名，例如 `adminAuth.ts`、`adminSession.ts`、`workbench.ts`；不得把请求逻辑分散到视图模板中。
- Vue 组件测试使用 `*.spec.ts` 或 `*.test.ts`，优先与被测组件同域存放；不得把测试用的身份、真实密钥或真实个人数据写入测试夹具。

### 4.4 Python 后端命名和存放

- Python 模块和文件使用 `snake_case`，例如 `deepseek_client.py`、`assessment_service.py`、`cloudbase_gateway.py`。
- 路由只放在 `backend/app/api/`；请求和响应模型只放在 `backend/app/schemas/`；固定规则和状态机只放在 `backend/app/domain/`；用例编排只放在 `backend/app/services/`；数据访问只放在 `backend/app/repositories/`；外部服务适配只放在 `backend/app/integrations/`。
- 令牌、密码、脱敏和授权逻辑放在 `backend/app/security/`；审计写入放在 `backend/app/audit/`；环境配置模型放在 `backend/app/config/`。
- 类名使用 PascalCase，函数和变量使用 `snake_case`，常量使用 `UPPER_SNAKE_CASE`。测试文件使用 `test_*.py`，放在 `backend/tests/`。
- 路由函数不得直接读写数据库、计算量表分数、决定安全分支或读取密钥。所有业务动作必须经过服务层，状态变化和审计写入必须属于同一个用例流程。

### 4.5 文档、配置和秘密

- 当前六份产品和工程规范保留在项目根目录；V2 细节保留在 `docs/v2/`，页面、状态、权限和验收规格保留在 `docs/superpowers/specs/`。
- API Key、微信密钥、CloudBase 密钥、后台密码哈希、会话密钥、真实身份和支持资源中的敏感配置只能放在服务端加密环境变量或密钥管理中。
- 密钥不得进入小程序包、后台构建产物、日志、审计详情、公开文档、测试夹具或版本管理跟踪文件。
- 环境配置必须明确区分演示、真实和未配置三种状态；`DEMO_MODE` 不能作为真实数据隔离的唯一措施。

## 5. 必须遵循的编码模式

### 5.1 学生端模式

- 使用原生小程序 `Page`、`Component` 和微信生命周期；本项目不使用 React 函数组件或 React Hooks。
- 页面只负责展示状态、收集用户动作和调用服务层；评分、权限、状态迁移、脱敏和安全规则不写在 WXML 或页面事件处理函数中。
- 组件必须显式处理正常、加载、处理中、禁用、空数据、网络失败、权限失败、会话失效和服务未配置状态。
- API 请求集中在 `services/`，结果和权限以服务端返回为准；未提交普通 UI 状态可以暂存于当前页面内存，敏感数据不得持久化。
- 提交类操作必须使用幂等键；按钮在请求处理中不可重复提交；网络失败不能把未确认的数据显示成已保存。
- 每日心情只允许当天首次保存；保存成功后当天不提供修改入口。未完成自测答案只保留客户端当前会话内存，完成或安全确认请求一次性提交必要数据。
- PHQ-9 第 9 题选择非零后必须立即进入安全确认。安全分支由固定规则和服务端状态保护，不能等待 AI，也不能由客户端自行改写为普通结果。

### 5.2 管理后台模式

- 使用 Vue 3 Composition API 和 `<script setup lang="ts">`；新组件不得使用 Options API。
- 使用 Pinia 管理会话、工作台和必要 UI 状态；页面离开或会话过期时清除任务详情等敏感状态。
- 使用 Zod 校验服务端响应和外部表单边界；不能只信任 TypeScript 类型声明或前端隐藏字段。
- W-02 永远保留“需要我处理 / 等待他人 / 最近处理”三个任务区块。W-03 永远使用“必要事实与脱敏内容 / 当前操作”两栏结构。
- 操作面板只展示当前服务端会话和任务状态允许的动作。前端显示的角色、按钮或任务状态不是权限来源。
- 并发冲突、无权限、会话过期、状态已变化和提交失败必须在页面上下文中明确展示，并切换为只读或可重试状态，不用全屏错误弹窗遮盖事实。
- 审计日志只读；演示重置必须在服务端确认当前为演示环境并写入审计。

### 5.3 Python 后端模式

- FastAPI 路由层只做认证依赖、输入校验、调用服务和响应序列化；业务规则不得堆在路由函数中。
- Pydantic 模型作为请求、响应和配置边界；API 统一使用 `/api/v1`、统一成功/失败响应封装和稳定错误码。
- `domain/` 中实现纯确定性评分、结果分层、安全分支、权限和状态机；不能把这些规则交给 AI 或前端。
- `services/` 编排一个完整业务动作，包括必要的数据写入、并发检查、幂等检查和审计事件；`repositories/` 不做产品判断。
- 外部微信、学校身份核验、DeepSeek 和 CloudBase 调用必须通过 `integrations/` 或明确的访问适配器，设置固定超时并返回可识别的依赖错误。
- 所有敏感字段读取、任务决定、删除、账户停止、身份授权和演示重置必须写最小必要审计；日志不写完整请求体、原始答案、完整树洞正文、身份密文或模型原始输入输出。
- 结果、状态和权限使用服务端枚举。并发写入使用版本或条件更新；状态已变化时返回 `409`，客户端转只读。
- 任何 API 失败都不能写入成功状态；DeepSeek 失败必须走固定结果文案或人工审核回退。

### 5.4 隐私和产品规则模式

- 学生真实身份只进入身份域；树洞只展示匿名展示名。后台默认只能看必要事实与脱敏内容，身份读取需要有效授权任务、范围和审计。
- 安全支持状态优先展示现实支持资源，不显示不必要的分数、历史、AI、真实身份或风险等级标签。
- PHQ-9、GAD-7 使用固定题目、固定计分和固定非诊断性表达；睡眠观察只输出三个观察维度，不计算临床总分。
- 树洞最终状态只能是公开、保护展示、暂不公开或转安全复核对应的固定状态机；AI 只能给建议，规则引擎和人工决定最终结果。
- 社区同意撤回后仍可浏览公开内容，但不能发帖或回应；已有内容不会自动删除。
- 账户停止使用进入 30 天恢复期；恢复期内不接受新记录、发帖或回应，期满按保留规则删除或不可识别化。

## 6. 设计系统令牌和界面基线

### 6.1 调色板

所有新界面优先引用 `FRONTEND_GUIDELINES.md` 的语义令牌，不得随意增加颜色。令牌与十六进制值如下：

| 令牌用途 | 十六进制 | 使用规则 |
| --- | --- | --- |
| 暖雾纸白背景 | `#F7F4EE` | 页面主背景 |
| 内容白 | `#FFFFFF` | 内容区、输入区、对比表面 |
| 深墨绿灰 | `#1F2D2B` | 标题、正文、关键数据 |
| 次级灰绿 | `#5F6E6A` | 次级说明、时间、辅助信息 |
| 弱化灰绿 | `#8C9A96` | 占位、禁用和次要说明，不用于唯一错误说明 |
| 静谧青 | `#2E6F68` | 主要按钮、当前导航、链接、主图形 |
| 深静谧青 | `#245B55` | 按下、焦点、深色文字按钮 |
| 浅青表面 | `#E8F0EC` | 选中项、轻提示、次级背景 |
| 青灰分隔线 | `#D7E4DF` | 1px 分隔线、表格线、输入边界 |
| 安全砖红 | `#B85C4A` | 少量安全支持提醒和危险操作文字 |
| 浅安全砖红 | `#F5E7E3` | 安全支持区域背景 |
| 谨慎金 | `#C58A3D` | 等待或注意提示，不表示风险等级 |
| 浅谨慎金 | `#F6EEDB` | 等待和未配置提示背景 |

使用颜色表达状态时，必须同时提供文字、图标或结构差异。禁止使用红黄绿表达心理风险等级；安全砖红只在安全支持或明确危险操作中小范围使用。

### 6.2 字体、字号和间距

- 字体栈固定为：`-apple-system, BlinkMacSystemFont, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif`。
- 字号刻度为 `12px / 14px / 16px / 18px / 20px / 24px / 28px / 32px`；默认正文 `16px`，正文行高 `26px`。
- 字重只使用 `400`（正文）、`500`（区块标题）、`600`（页面标题和重要动作）；不使用 `700` 以上作为常规层级。
- 间距只能使用 `4px / 8px / 12px / 16px / 20px / 24px / 32px / 40px / 48px / 64px`。
- 手机左右边距：宽度 360–392px 使用 `20px`，393–430px 使用 `24px`，320–359px 可降为 `16px`。
- 后台默认左右边距 `40px`，栏间距 `24px` 或 `32px`，表格行高至少 `52px`，交互热区至少 `44px × 44px`。
- 按钮、输入框和轻容器圆角 `8px`，标签和小提示 `4px`；不得使用超过 `12px` 的大圆角卡片或把整页内容胶囊化。
- 默认不使用阴影；弹层只允许使用轻微阴影建立层级。禁止发光、内阴影、玻璃拟态和厚重卡片阴影。

### 6.3 适配和视觉禁用项

- 学生端按 320–430px 手机宽度设计，超过 430px 保持可读最大内容列，不无限拉伸。
- 后台标准画布为 `1440×900`，`1280px` 为最小工作宽度。低于 `1280px` 只显示电脑浏览器提示，不展示可操作后台，不改成移动端底部导航。
- 禁止渐变、发光、新闻式信息流、游戏化勋章、连续打卡奖励、自动播放声音、强制震动和红色闪烁。
- 图形仅限分数定位尺、回答指纹、单模块历史轨迹、近期记录时间带和睡眠三维观察线；必须有文本摘要和无图形降级状态，不做跨量表总分、雷达图或综合风险仪表盘。
- 不把分数作为安全状态唯一视觉焦点；安全支持页先给现实资源和行动路径。

## 7. 明确禁止的操作

以下行为禁止执行，除非当前规范经过明确更新并由用户授权：

1. 禁止使用 Node.js、JavaScript 云函数或其他语言替代 Python 3.11 业务后端。
2. 禁止让学生端或后台直连 CloudBase 数据库管理接口、读取高权限接口或直接调用 DeepSeek。
3. 禁止把 `DEEPSEEK_API_KEY`、微信密钥、密码哈希、令牌、真实身份或后台备注写入前端、日志、审计详情、测试数据或版本管理文件。
4. 禁止用 AI 评分、分层、诊断、预测风险、决定安全处置、决定帖子最终公开状态或替代工作人员判断。
5. 禁止把 PHQ-9、GAD-7 和睡眠观察合并成综合分、风险仪表盘、跨模块排名或医疗结论。
6. 禁止在安全支持状态显示不必要的分数、历史、AI 内容、真实身份或风险等级标签。
7. 禁止在服务端保存未完成自测答案，禁止将未完成答案写入 AI、审计正文或前端持久化存储。
8. 禁止为每日短句运行时联网抓取、调用模型生成或无出处展示网络内容。
9. 禁止引入 shadcn/ui、Element Plus、Ant Design Vue、Naive UI、大型 UI 组件库、高级图表库、Tailwind、第三方请求库或未批准的 AI SDK。
10. 禁止使用红黄绿颜色表达心理风险，禁止用颜色作为唯一状态信息。
11. 禁止使用 HTML `style` 属性、Vue `:style` 或其他内联样式；所有样式必须通过 WXSS/CSS、设计令牌、语义类名和项目组件实现。
12. 禁止在业务代码中使用未解释的 `any`、随意的 `as unknown as`、硬编码 API URL、硬编码密钥或未经契约定义的错误字符串。
13. 禁止在路由函数中直接访问数据库或写业务规则，禁止在页面中复制评分、权限和安全状态逻辑。
14. 禁止因视觉预览中的不可点击装饰元素而擅自新增产品功能、导航或接口。
15. 禁止安装 Lieflat Charts Skill 或其他 Skill；只有用户明确要求且任务确实进入对应能力范围时，才可按平台规则处理。
16. 禁止在未读取 `progress.txt`、`lessons.md` 和相关完整规范前修改项目文件。

## 8. 参考规范文档清单

以下文件是当前实现、审查和验收的完整参考集合。根目录六份文档是可执行总规范；`docs/v2/` 和 `docs/superpowers/specs/` 的 Markdown 文件提供领域细节。所有链接均相对于项目根目录。

### 8.1 根目录六份总规范

- [PRD.md](PRD.md)：产品范围、目标、角色、功能需求、数据边界和验收口径。
- [APP_FLOW.md](APP_FLOW.md)：学生端和后台每个页面的触发、导航、成功、错误和状态路径。
- [TECH_STACK.md](TECH_STACK.md)：技术选型、精确版本、平台 API、环境变量、部署和技术禁用项。
- [FRONTEND_GUIDELINES.md](FRONTEND_GUIDELINES.md)：视觉令牌、组件、排版、响应式和可访问性规则。
- [BACKEND_STRUCTURE.md](BACKEND_STRUCTURE.md)：数据库集合、字段、关系、API 合约、认证、权限、状态和 Python 分层。
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)：从工程初始化到部署和验收的实现步骤；不替代用户的协作流程。

### 8.2 `docs/v2/` 领域规范

- [V2_CONFIRMED_PRODUCT_DECISIONS.md](docs/v2/V2_CONFIRMED_PRODUCT_DECISIONS.md)：当前已确认的产品、UI/UX、权限、数据和部署决策。
- [V2_TECHNICAL_ARCHITECTURE_AND_DEPLOYMENT.md](docs/v2/V2_TECHNICAL_ARCHITECTURE_AND_DEPLOYMENT.md)：三端架构、Python 云函数、CloudBase 和部署边界。
- [V2_AI_INTERFACE_AND_PROMPT_SPEC.md](docs/v2/V2_AI_INTERFACE_AND_PROMPT_SPEC.md)：DeepSeek 接口、固定提示词、输入脱敏、输出校验、回退和审计规则。
- [V2_DAILY_QUOTE_LIBRARY.md](docs/v2/V2_DAILY_QUOTE_LIBRARY.md)：每日短句库的来源、出处、版本和展示规则。
- [V2_ASSESSMENT_MEDICAL_EVIDENCE_AND_REFERENCES.md](docs/v2/V2_ASSESSMENT_MEDICAL_EVIDENCE_AND_REFERENCES.md)：PHQ-9、GAD-7、睡眠观察的依据、非诊断表达和上线前证据检查。

### 8.3 `docs/superpowers/specs/` 页面、状态和验收规范

- [2026-07-27-assessment-design.md](docs/superpowers/specs/2026-07-27-assessment-design.md)：自测模块设计。
- [2026-08-12-admin-content-review-workbench-design.md](docs/superpowers/specs/2026-08-12-admin-content-review-workbench-design.md)：后台内容审核工作台。
- [2026-08-12-assessment-result-page-design.md](docs/superpowers/specs/2026-08-12-assessment-result-page-design.md)：自测结果页。
- [2026-08-24-admin-control-layer-design.md](docs/superpowers/specs/2026-08-24-admin-control-layer-design.md)：后台控制层和权限操作。
- [2026-08-24-admin-safety-support-identity-followup-design.md](docs/superpowers/specs/2026-08-24-admin-safety-support-identity-followup-design.md)：安全支持、身份授权和跟进任务。
- [2026-08-26-admin-workbench-unified-task-design.md](docs/superpowers/specs/2026-08-26-admin-workbench-unified-task-design.md)：W-02 统一任务工作台和三任务区块。
- [2026-08-26-assessment-center-answer-safety-design.md](docs/superpowers/specs/2026-08-26-assessment-center-answer-safety-design.md)：自测答题和 PHQ-9 第 9 题安全确认。
- [2026-08-26-assessment-high-fidelity-wireframes.md](docs/superpowers/specs/2026-08-26-assessment-high-fidelity-wireframes.md)：自测高保真页面结构。
- [2026-08-26-audit-demo-data-design.md](docs/superpowers/specs/2026-08-26-audit-demo-data-design.md)：审计日志和演示数据隔离、重置规则。
- [2026-08-26-data-state-interface-boundary-design.md](docs/superpowers/specs/2026-08-26-data-state-interface-boundary-design.md)：数据状态、接口和前后端边界。
- [2026-08-26-end-to-end-prototype-acceptance-matrix.md](docs/superpowers/specs/2026-08-26-end-to-end-prototype-acceptance-matrix.md)：端到端原型验收矩阵。
- [2026-08-26-final-copy-prototype-task-list.md](docs/superpowers/specs/2026-08-26-final-copy-prototype-task-list.md)：最终文案和原型任务清单。
- [2026-08-26-first-batch-high-fidelity-wireframes.md](docs/superpowers/specs/2026-08-26-first-batch-high-fidelity-wireframes.md)：首批高保真线框。
- [2026-08-26-high-fidelity-prototype-execution-checklist.md](docs/superpowers/specs/2026-08-26-high-fidelity-prototype-execution-checklist.md)：高保真原型执行检查清单。
- [2026-08-26-my-support-deletion-design.md](docs/superpowers/specs/2026-08-26-my-support-deletion-design.md)：我的、支持资源和删除流程。
- [2026-08-26-onboarding-identity-today-design.md](docs/superpowers/specs/2026-08-26-onboarding-identity-today-design.md)：首次使用、身份核验和今日路径。
- [2026-08-26-page-inventory-navigation-design.md](docs/superpowers/specs/2026-08-26-page-inventory-navigation-design.md)：页面清单和导航结构。
- [2026-08-26-permission-visibility-matrix-design.md](docs/superpowers/specs/2026-08-26-permission-visibility-matrix-design.md)：权限和可见性矩阵。
- [2026-08-26-prototype-final-closure-regression-design.md](docs/superpowers/specs/2026-08-26-prototype-final-closure-regression-design.md)：原型最终收口和回归检查。
- [2026-08-26-prototype-integration-review-design.md](docs/superpowers/specs/2026-08-26-prototype-integration-review-design.md)：原型整合审查。
- [2026-08-26-result-history-high-fidelity-wireframes.md](docs/superpowers/specs/2026-08-26-result-history-high-fidelity-wireframes.md)：结果与历史高保真线框。
- [2026-08-26-treehole-pages-design.md](docs/superpowers/specs/2026-08-26-treehole-pages-design.md)：树洞首页、发布、详情和状态页。
- [2026-08-26-v2-scope-freeze-demo-boundary.md](docs/superpowers/specs/2026-08-26-v2-scope-freeze-demo-boundary.md)：V2 范围冻结和演示边界。
- [2026-08-26-visual-baseline-first-prototype-design.md](docs/superpowers/specs/2026-08-26-visual-baseline-first-prototype-design.md)：首版视觉基线和原型规则。
- [2026-08-27-global-components-state-variants-design.md](docs/superpowers/specs/2026-08-27-global-components-state-variants-design.md)：全局组件和状态变体。

文档审查时必须同时核对这些文件中的重复、过时表述、字段边界、状态迁移和验收条件。当前标准已经收口的决策（例如 Python 后端、未完成答案不落库、每日心情当天不可修改、Q9 非零立即安全确认、W-02 三任务区块和 W-03 两栏结构）不得被旧文档或原型覆盖。
