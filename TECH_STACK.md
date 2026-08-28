# 心语 V2 技术栈规范

## 0. 文档信息

- 文档版本：TECH-1.0
- 锁定日期：2026-08-28
- 后端主语言：Python
- 小程序部署工具：微信开发者工具
- 文档状态：开发前技术基线
- 版本解释：本文列出的第三方依赖使用精确版本号；CloudBase 云端运行时的补丁版本由平台维护，因此按平台公开的 Python 3.11 运行时锁定，不人为假定不可见的补丁号

## 1. 总体技术选择

心语 V2 由三个彼此分离的运行单元组成：

| 运行单元 | 技术形态 | 运行位置 | 责任 |
| --- | --- | --- | --- |
| 学生端 | 原生微信小程序、TypeScript、WXML、WXSS | 微信客户端 | 今日、自测、树洞、我的 |
| 业务后端 | Python 3.11、FastAPI 0.128.8、HTTP 云函数 | CloudBase | 认证、规则、数据、权限、审计、AI 调用 |
| 管理后台 | Vue 3、TypeScript、Vite 桌面单页应用 | 浏览器与 CloudBase 静态托管 | W-01 至 W-05 |

数据库使用 CloudBase 文档型数据库。所有端都通过业务后端访问业务数据，不让学生端或管理后台直接调用数据库管理接口。

## 2. 精确版本清单

### 2.1 本地与部署工具

| 工具 | 精确版本或平台版本 | 用途 | 约束 |
| --- | --- | --- | --- |
| 微信开发者工具 | 2.01.2510290 | 小程序预览、真机核验、上传 | 这是当前项目的参考版本；开发机不得低于该版本验证结果 |
| Node.js | 22.21.0 | 管理后台构建 | 只用于前端工具链，不运行 Python 后端 |
| npm | 10.9.4 | 管理后台包安装和脚本执行 | 使用 package-lock.json 锁定安装结果 |
| Python | 3.11.11 | 后端本地开发与测试 | CloudBase 云端选择 Python 3.11 运行时 |
| Git | 2.50.1 | 版本管理 | 不在本文规定分支和提交流程 |

微信小程序基础库属于微信客户端平台能力，不由 npm 锁定。验收基线为支持 CloudBase 和本项目所用原生接口的基础库，最低能力参考为 2.2.3；真机验收必须记录实际微信版本和基础库版本。

### 2.2 学生端依赖

学生端不使用大型 UI 框架、Tailwind、图表库、网络请求库或 AI SDK，组件使用微信原生组件和项目内组件。

| 依赖 | 版本 | 类型 | 用途 |
| --- | --- | --- | --- |
| TypeScript | 7.0.2 | 开发依赖 | 学生端业务代码类型检查与编译 |
| miniprogram-api-typings | 5.2.3 | 开发依赖 | 微信小程序 API 类型声明 |

学生端调用微信能力只使用原生接口：微信登录、网络请求、云能力初始化、页面导航、系统剪贴板和拨号/打开链接等。不得引入 axios、request 封装包、第三方登录包或客户端 DeepSeek 包。

### 2.3 管理后台依赖

| 依赖 | 精确版本 | 类型 | 用途 |
| --- | --- | --- | --- |
| vue | 3.5.42 | 运行依赖 | 管理后台视图层 |
| vue-router | 5.3.0 | 运行依赖 | W-01 至 W-05 路由 |
| pinia | 4.0.3 | 运行依赖 | 会话、工作台、任务和 UI 状态 |
| zod | 4.4.3 | 运行依赖 | API 响应和表单边界校验 |
| vite | 8.2.2 | 开发依赖 | 开发服务器与生产构建 |
| @vitejs/plugin-vue | 6.0.8 | 开发依赖 | Vue 单文件组件构建 |
| typescript | 7.0.2 | 开发依赖 | 类型检查与构建 |
| vue-tsc | 3.3.11 | 开发依赖 | Vue 类型检查 |
| vitest | 4.1.11 | 开发依赖 | 单元测试和组件测试 |
| jsdom | 30.0.1 | 开发依赖 | 浏览器环境测试 |
| @testing-library/vue | 8.1.0 | 开发依赖 | Vue 组件行为测试 |
| eslint | 10.9.1 | 开发依赖 | JavaScript、TypeScript 代码检查 |
| eslint-plugin-vue | 10.10.0 | 开发依赖 | Vue 规则检查 |
| @typescript-eslint/parser | 8.68.0 | 开发依赖 | TypeScript 语法解析 |
| @typescript-eslint/eslint-plugin | 8.68.0 | 开发依赖 | TypeScript 规则 |
| eslint-config-prettier | 10.1.8 | 开发依赖 | 关闭与格式化冲突的规则 |
| prettier | 3.9.6 | 开发依赖 | 代码和样式格式化 |
| @types/node | 26.4.0 | 开发依赖 | 构建脚本的 Node 类型 |

后台不使用 shadcn/ui、Element Plus、Ant Design Vue、Naive UI 或其他大型组件库。原因是 V2 的后台需要严格落实已经冻结的 W-01 至 W-05 桌面工作台视觉和数据暴露边界；组件由项目内基础组件实现，避免第三方组件默认交互覆盖产品规则。

### 2.4 Python 后端依赖

| 依赖 | 精确版本 | 类型 | 用途 |
| --- | --- | --- | --- |
| fastapi | 0.128.8 | 运行依赖 | HTTP 路由、请求校验、响应序列化 |
| pydantic | 2.13.4 | 运行依赖 | 请求、响应和配置模型 |
| httpx | 0.28.1 | 运行依赖 | DeepSeek 与 CloudBase HTTP API 出站请求 |
| uvicorn | 0.39.0 | 运行依赖 | CloudBase HTTP 函数的 9000 端口启动服务 |
| pytest | 8.4.2 | 开发依赖 | 后端单元与契约测试 |
| pytest-asyncio | 1.2.0 | 开发依赖 | 异步接口测试 |
| ruff | 0.16.5 | 开发依赖 | Python 格式化与静态检查 |
| mypy | 1.19.1 | 开发依赖 | Python 类型检查 |
| pip-tools | 7.6.1 | 构建依赖 | 从直接依赖生成完整 requirements.lock |

后端不使用 DeepSeek 官方或第三方 Python SDK，直接使用 httpx 调用 OpenAI 兼容接口，以便锁定请求字段、超时和脱敏边界。后端不使用 ORM；通过项目内的文档数据库访问适配器调用 CloudBase HTTP API。

Python 的传递依赖必须在实施阶段由 Python 3.11.11 环境生成完整锁文件，并在构建中使用锁文件安装。直接依赖版本不得使用脱字符号、波浪号或 latest 标签。

## 3. 平台 API 与外部接口

### 3.1 微信小程序平台接口

学生端允许使用以下原生能力：

| 能力 | 接口 | 用途 | 数据限制 |
| --- | --- | --- | --- |
| 登录 | 微信登录接口 | 获取一次性登录凭证并换取业务会话 | 凭证只在服务端交换，不写入日志 |
| 网络 | 微信网络请求接口 | 调用项目业务 API | 只请求配置的 HTTPS 域名 |
| 导航 | 小程序导航接口 | 页面跳转和返回 | 关键流程由服务端状态保护 |
| 提示 | 原生提示接口 | 确认、错误和成功提示 | 不在系统提示中放完整敏感内容 |
| 拨号/链接 | 微信允许的系统能力 | 打开支持资源 | 资源必须来自环境配置 |

小程序项目不直接调用 CloudBase 数据库管理 API、不直接调用 DeepSeek、不持有 DeepSeek API Key。

### 3.2 项目业务 API

业务 API 的公共前缀为 /api/v1，传输格式为 HTTPS JSON。完整端点、字段和错误码见 [后端结构文档](BACKEND_STRUCTURE.md)。

统一响应格式为：

~~~json
{
  "request_id": "请求编号",
  "data": {},
  "error": null
}
~~~

失败响应把 data 置为 null，并在 error 中返回稳定错误码、用户可读消息和是否可以重试的标记。服务端不得把堆栈、数据库错误、密钥或未脱敏数据返回客户端。

### 3.3 DeepSeek 接口

模型配置锁定如下：

| 配置项 | 值 |
| --- | --- |
| API 基地址 | https://api.deepseek.com |
| 路径 | /chat/completions |
| 请求模型名 | deepseek-v4-flash |
| 解析模型版本 | DeepSeek-V4-Flash-0731 |
| 请求方式 | HTTPS POST |
| 输出格式 | JSON Object |
| 温度 | 0.2 |
| 流式输出 | false |
| 连接及读取总超时 | 8 秒 |
| 自动重试 | 0 次，由业务固定规则或人工流程接管 |
| API Key | 服务端环境变量 DEEPSEEK_API_KEY，由用户填写 |
| 提示词版本 | xinyu-v2-system-v1 |

允许的请求结构为：

~~~json
{
  "model": "deepseek-v4-flash",
  "messages": [
    {"role": "system", "content": "服务端固定系统提示词"},
    {"role": "user", "content": "经过白名单和脱敏的任务内容"}
  ],
  "temperature": 0.2,
  "response_format": {"type": "json_object"},
  "stream": false
}
~~~

不传完整 PHQ-9、GAD-7 或睡眠答案，不传姓名、学号、真实身份、完整未脱敏树洞正文、安全确认原文、后台审计备注或 API Key。AI 输出必须经过 JSON 结构校验、枚举校验和固定策略复核；校验失败视为 AI 不可用。

固定系统提示词、任务白名单、输出模式和禁止事项见 [AI 接口与提示词规范](docs/v2/V2_AI_INTERFACE_AND_PROMPT_SPEC.md)。

### 3.4 CloudBase 平台接口

| 平台能力 | 采用方式 | 说明 |
| --- | --- | --- |
| 云函数 | Python 3.11 HTTP 云函数 | FastAPI 应用监听 9000 端口 |
| 文档数据库 | 后端 HTTP 访问适配器 | 只允许后端服务凭据访问 |
| 静态托管 | CloudBase 静态网站托管 | 发布后台构建产物 |
| 环境 | 演示环境与真实授权环境 | 使用不同环境 ID、密钥和数据命名空间 |

Python HTTP 函数发布包必须有平台启动文件 scf_bootstrap，启动命令指向应用入口并监听 9000 端口。微信开发者工具负责小程序项目的预览、真机验证和上传；如果当前工具版本不提供 Python 函数模板，Python 函数按 CloudBase Python 上传入口发布，不得伪装成其他运行时函数。

## 4. 环境变量与配置

配置位、演示/真实授权/未配置三种状态、存放边界和填写审查规则统一登记在 [CONFIGURATION_REGISTRY.md](CONFIGURATION_REGISTRY.md)。本节保留技术栈层面的变量名称；任何真实值都不得写入版本管理文件。

### 4.1 小程序构建配置

| 变量 | 演示 | 真实 | 是否提交代码 |
| --- | --- | --- | --- |
| WECHAT_MINIPROGRAM_APPID | 用户填写 | 用户填写 | 只允许非秘密构建配置 |
| API_BASE_URL | 演示 HTTPS 地址 | 真实 HTTPS 地址 | 不写死在业务页面 |
| CLOUDBASE_ENV_ID | 演示环境 ID | 真实环境 ID | 只作为环境配置 |

### 4.2 后端配置

| 变量 | 用途 | 存储规则 |
| --- | --- | --- |
| WECHAT_APPID | 微信登录交换 | 服务端密钥配置 |
| WECHAT_APPSECRET | 微信登录交换 | 只在服务端密钥配置 |
| CLOUDBASE_ENV_ID | 数据库和云函数环境 | 环境级配置 |
| CLOUDBASE_API_KEY | CloudBase HTTP 访问 | 只在服务端密钥配置 |
| DEEPSEEK_API_KEY | DeepSeek 调用 | 只在服务端密钥配置 |
| ADMIN_PASSWORD_HASH | 固定后台账号密码哈希 | 只在服务端密钥配置 |
| ADMIN_SESSION_SECRET | 后台会话签名或哈希 | 只在服务端密钥配置 |
| SCHOOL_IDENTITY_PROVIDER_URL | 学校身份核验适配器 | 未配置时必须显示未配置 |
| SUPPORT_RESOURCE_VERSION | 支持资源版本 | 环境配置 |
| DEMO_MODE | 是否为演示环境 | 必须由环境标记决定 |

所有配置位允许由用户后续填写，但未配置不代表功能已实现。缺少真实支持资源、身份核验或 DeepSeek 密钥时只能进入演示或明确的未配置状态。

## 5. 前端构建和运行约束

### 5.1 学生端

- 页面使用原生小程序目录和 TypeScript 文件；
- WXSS 使用项目设计变量，不复制后台 CSS；
- API 请求集中在学生端服务层，页面不拼接数据库请求；
- 所有结果、状态和权限以服务端返回为准；
- 本地只保留非敏感 UI 状态和未提交普通文本，不能持久化姓名、学号、完整答案、安全确认或后台备注。

### 5.2 管理后台

- 使用 Vue 3 单页应用，不使用服务端渲染；
- 路由只覆盖 W-01 至 W-05 和必要的错误状态；
- 状态管理只保存当前会话、任务摘要、版本号和非敏感 UI 状态；
- 任务详情离开页面或会话过期时清理；
- 标准画布 1440×900，最小工作宽度 1280px；
- 小于 1280px 显示电脑浏览器提示，不改变为移动导航。

## 6. 开发、构建和部署命令约定

命令名称固定，实际目录在开发开始前按实施计划创建：

~~~text
前端安装：npm ci
前端类型检查：npm run typecheck
前端格式检查：npm run format:check
前端代码检查：npm run lint
前端测试：npm run test
前端构建：npm run build

后端安装：python -m pip install --requirement requirements.lock
后端检查：ruff check .
后端格式检查：ruff format --check .
后端类型检查：mypy .
后端测试：pytest
~~~

这些命令只规定技术接口，不替代用户后续提供的开发流程、分支策略、提交策略、测试分层或任务拆分规则。

## 7. 技术禁用清单

- 禁止在小程序或后台前端写入 DeepSeek API Key。
- 禁止使用 Node.js 作为业务后端运行时；Python 3.11 是唯一后端运行时。
- 禁止客户端直连 CloudBase 数据库管理接口。
- 禁止引入会自动生成诊断、风险标签或跨量表总分的第三方心理分析包。
- 禁止使用红黄绿颜色表达风险等级。
- 禁止在首版加入大型 UI 组件库和高级图表库。
- 禁止运行时抓取网络短句或调用模型生成每日短句。
- 禁止把演示数据开关作为真实数据隔离的唯一手段。

## 8. 官方依据

- [CloudBase 云函数运行时支持](https://docs.cloudbase.net/cloud-function/runtime-support)：确认 Python 3.11 运行时以及 Python HTTP 函数支持。
- [CloudBase Python HTTP 云函数快速开始](https://docs.cloudbase.net/cloud-function/quickstart/httpfunc/python)：确认 Python HTTP 函数打包、依赖和发布方式。
- [CloudBase 云函数代码编写与启动文件](https://docs.cloudbase.net/cloud-function/develop/how-to-writing-functions-code)：确认 scf_bootstrap、9000 端口和 Python HTTP 入口约束。
- [CloudBase 静态网站托管](https://docs.cloudbase.net/hosting/quick-start)：确认后台静态构建产物托管方式。
- [DeepSeek API 文档](https://api-docs.deepseek.com/zh-cn/)：确认 Chat Completions 接口形态。
- [DeepSeek JSON 输出](https://api-docs.deepseek.com/zh-cn/guides/json_mode/)：确认 JSON Object 输出方式。
- [Vue TypeScript 指南](https://vuejs.org/guide/typescript/overview)：确认 Vue 3 与 TypeScript 的组合方式。
- [Vite 指南](https://vite.dev/guide/)：确认后台构建工具。
