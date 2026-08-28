# 心语 V2 技术架构与微信部署规范

## 1. 文档信息

- 版本：architecture-v1
- 冻结日期：2026-08-27
- 当前状态：平台、运行边界和部署口径已确认；AppID、EnvID、域名与密钥由用户后续填写
- 适用范围：学生端微信小程序、CloudBase 共享后端、独立 Web 管理后台

本文定义技术形态和部署边界，不制定开发顺序、分支策略、提交策略、测试策略、任务拆分或子代理方式。具体开发流程以用户后续提供的流程为准。

## 2. 总体架构

```text
学生微信
  └─ 原生微信小程序
       └─ CloudBase 云函数（唯一业务入口）
            ├─ 文档型数据库
            ├─ 审计与配置
            └─ DeepSeek API（仅服务端、仅允许任务）

桌面浏览器
  └─ 独立 Web 管理后台（CloudBase 静态网站托管）
       └─ 同一组受权限保护的 CloudBase 后端能力
```

学生端与后台共享业务规则和数据状态，但不共享“返回全部字段”的通用接口。每个端、账号能力和任务只获取最小必要数据投影。

## 3. 技术形态

首版技术栈冻结为：

| 层 | 技术 |
| --- | --- |
| 学生端 | 原生微信小程序 + TypeScript + WXML + WXSS |
| 管理后台 | Vue 3 + TypeScript + Vite，单页应用 |
| 云函数 | CloudBase Python 3.11 HTTP 云函数 + FastAPI 0.128.8 + Uvicorn 0.39.0 |
| 数据库 | CloudBase 文档型数据库 |
| AI 接口 | 云函数调用 DeepSeek OpenAI 兼容 Chat Completions |
| Web 托管 | CloudBase 静态网站托管 |

管理后台不需要 SSR，不引入 Nuxt。首版不依赖大型 UI 组件库，使用项目内少量基础组件落实已经冻结的桌面视觉；这避免组件库默认卡片、弹窗和响应式规则改变 W-01 至 W-05。云函数基线固定为 CloudBase Python 3.11 运行时，HTTP 入口监听平台要求的 9000 端口，并使用平台要求的启动文件。升级 Python 大版本、FastAPI 主版本或 Vue/Vite 主版本需要单独记录兼容性验证。Node.js 只作为后台 Web 的本地构建工具，不作为业务后端运行时。

### 3.1 学生端

- 原生微信小程序，不打包为 App 或 H5；
- 页面、组件和路由遵守微信小程序运行约束；
- 小程序只调用 CloudBase 云函数，不直连数据库管理接口、DeepSeek 或后台 Web；
- AppID 占位：`${WECHAT_MINIPROGRAM_APPID}`；
- CloudBase 环境 ID 占位：`${CLOUDBASE_ENV_ID}`。

### 3.2 共享后端

首版采用 CloudBase：

- Python 3.11 HTTP 云函数承载认证后的业务命令、权限检查、状态迁移、脱敏、AI 调用和审计写入；
- FastAPI 只负责 HTTP 路由、请求校验和响应序列化；业务规则不写在路由函数中；
- CloudBase 文档型数据库通过后端数据访问适配层访问；前端和管理后台不直连数据库管理接口；
- Python 函数包必须包含平台启动文件 scf_bootstrap，并按 CloudBase Python 函数规范携带已锁定的依赖；
- 文档型数据库承载分域业务数据；
- 云环境配置或密钥管理保存 API Key、真实支持资源和环境开关；
- 如后续出现长连接或超出云函数约束的明确需求，再单独评审云托管；首版不以云托管作为前置条件。

前端不得信任自己提交的账号能力、身份、分数、公开状态或审计字段。评分、权限、状态迁移、删除边界和演示隔离均在服务端再次校验。

### 3.3 独立 Web 管理后台

- 独立桌面 Web UI，部署在 CloudBase 静态网站托管；
- 与小程序共享后端，但使用后台专用会话和权限投影；
- 标准画布 1440×900，最小工作宽度 1280px；
- 低于 1280px 只显示电脑浏览器提示；
- 后台 URL/自定义域名占位：`${ADMIN_WEB_ORIGIN}`；
- 工程目录、包管理器和代码职责基线见根目录 IMPLEMENTATION_PLAN.md 与 TECH_STACK.md；用户后续开发流程只补充协作、分支、提交、测试和任务拆分，不改变运行时边界；技术框架不再待选，产品页面固定为 W-01 至 W-05。

## 4. 数据域

数据库至少按以下逻辑域隔离；实际集合名可在开发计划中确定：

| 数据域 | 内容 | 关键限制 |
| --- | --- | --- |
| 身份账户 | 核验状态、内部账户引用、同意版本 | 不向社区和 AI 暴露 |
| 私密观察 | 每日心情 | 仅本人；不触发后台任务 |
| 自测快照 | 固定答案、规则版本、结果快照 | 普通记录仅本人可见 |
| 匿名社区 | 匿名身份快照、帖子、回应、公开状态 | 与真实身份分离 |
| 内容审核 | 脱敏内容、规则结果、人工决定 | 不保存无必要未脱敏副本 |
| 安全支持 | 最小安全事实、已展示资源、受限状态 | 仅演示或授权模式进入后台 |
| 身份授权 | 申请、字段范围、有效期、撤回 | P3 短时最少显示 |
| 工作任务 | 认领、状态版本、处理结果 | 防并发覆盖 |
| 审计 | 操作者、对象、动作、范围、结果 | 只读，不复制完整敏感内容 |
| 运行配置 | 支持资源、内容库版本、开关 | 分环境管理 |

身份域与其他域只通过不可逆内部引用关联；姓名、学号不能成为跨域查询键。

## 5. 环境与数据隔离

至少提供：

- 开发/演示环境：只允许固定演示账号和合成数据；
- 真实授权环境：只有在学校、隐私、资源和专业门槛完成后启用。

两类环境使用不同 EnvID、密钥、数据库命名空间、支持资源配置和后台入口。代码中的 `demo` 标志不能替代环境级隔离。演示环境不能查询真实环境，真实环境也不能混入演示对象。

开发占位：

```text
WECHAT_MINIPROGRAM_APPID=
CLOUDBASE_ENV_ID_DEMO=
CLOUDBASE_ENV_ID_PRODUCTION=
ADMIN_WEB_ORIGIN_DEMO=
ADMIN_WEB_ORIGIN_PRODUCTION=
DEEPSEEK_API_KEY=
```

这些值不得提交到公开前端包。生产环境未完成授权前保持未配置和不可进入。

## 6. 接口边界

业务接口按命令和最小投影设计，不开放通用记录编辑：

- 获取/保存每日心情；
- 开始、完成或丢弃自测会话；
- 读取固定结果、历史与当前支持资源；
- 提交、撤回或删除树洞内容；
- 获取公共树洞与作者私密状态；
- 认领任务、提交内容决定、安全支持记录、身份授权和跟进事实；
- 读取只读审计与重置演示数据。

所有改变状态的请求携带对象当前版本，由服务端做权限、模式、状态和幂等校验。冲突时返回只读事实状态，前端不得覆盖新状态。

## 7. AI 调用边界

DeepSeek 只能由云函数调用。调用前完成字段白名单、去身份化和树洞文本遮罩；调用后完成 JSON 结构校验和策略复核。禁止把 API Key、完整答案、真实身份、未脱敏正文、审计备注或安全确认内容发送给模型。详细契约见 [AI 规范](V2_AI_INTERFACE_AND_PROMPT_SPEC.md)。

## 8. 微信开发者工具部署口径

### 8.1 小程序

部署入口采用微信开发者工具：

1. 使用用户填写的 AppID 打开原生小程序项目；
2. 选择对应 CloudBase 环境；
3. 在开发者工具中预览和真机核验；
4. 小程序代码通过开发者工具预览、真机核验和上传；
5. 小程序代码通过开发者工具“上传”生成待提交版本；
6. 后续在微信公众平台完成体验版、审核与发布。

“使用微信开发者工具部署”不表示真实密钥写在开发者工具或小程序代码中，也不表示后台 Web 被压缩进小程序。

### 8.2 管理后台 Web

后台 Web 构建后部署到与小程序关联的 CloudBase 环境的静态网站托管。静态网站托管发布入口位于 CloudBase 控制台；可以上传构建产物，也可以在用户后续流程允许时使用 CloudBase CLI。首版规范只要求：

- 后台构建产物与小程序包分离；
- 绑定 HTTPS 域名或环境默认域名；
- 后台专用会话、跨域来源和权限规则显式配置；
- 演示与真实环境使用不同入口；
- 低于 1280px 显示桌面提示。

### 8.3 云函数与数据库

微信开发者工具是小程序项目的统一预览和上传入口。Python 云函数使用同一 CloudBase 环境，但必须按 CloudBase Python HTTP 云函数的打包规范发布：将业务包、scf_bootstrap 和已锁定依赖上传到 CloudBase 函数部署入口。若当前版本的微信开发者工具不提供 Python 运行时模板，不得把 Python 包伪装成其他运行时函数；应使用 CloudBase 控制台提供的 Python 运行时上传入口完成发布，随后回到微信开发者工具验证小程序调用。数据库集合、索引和权限规则属于后端部署内容，不能依赖前端自动创建真实生产数据结构。

## 9. 配置与秘密

- API Key、EnvID、生产域名、真实热线和校内联系人均为环境配置；
- 错误日志不得打印密钥、完整请求体、原始自测答案、未脱敏正文或 P3 身份字段；
- 小程序本地存储不保存未完成自测、姓名/学号草稿、后台备注或 DeepSeek 凭据；
- Web 浏览器不持久化未提交敏感输入；会话过期后立即隐藏敏感内容；
- 每次读取 P3 字段都写入审计。

## 10. 运行失败边界

- AI 失败：固定规则或人工确认接管；
- 支持资源未配置：显示未配置状态，不虚构数据；
- 身份核验不可用：不伪造已核验，不允许进入私密记录或发布；
- 某个首页区段失败：保留其他区段；
- 状态提交冲突：页面只读并显示当前事实；
- 演示重置失败：不影响真实命名空间，也不显示部分成功为全部成功。

## 11. 上线前外部配置门槛

- 小程序 AppID、主体、类目、隐私保护指引与微信审核材料；
- CloudBase 付费方案、两个环境的 EnvID、数据库权限和备份责任；
- 后台域名、HTTPS、允许来源和账号管理；
- DeepSeek API Key、预算、并发、超时与供应商条款；
- 校内真实身份核验接口与数据保存期限；
- 真实支持资源和安全响应授权。

## 12. 官方资料

- DeepSeek API：https://api-docs.deepseek.com/zh-cn/
- DeepSeek JSON Output：https://api-docs.deepseek.com/zh-cn/guides/json_mode/
- CloudBase 功能与场景：https://cloud.tencent.com/document/product/876/40406
- CloudBase 创建环境：https://docs.cloudbase.net/quick-start/create-env
- CloudBase 云函数快速开始：https://docs.cloudbase.net/cloud-function/quick-start
- CloudBase 云函数运行时支持：https://docs.cloudbase.net/cloud-function/runtime-support
- CloudBase Python HTTP 云函数快速开始：https://docs.cloudbase.net/cloud-function/quickstart/httpfunc/python
- CloudBase 云函数代码编写与启动文件：https://docs.cloudbase.net/cloud-function/develop/how-to-writing-functions-code
- CloudBase 静态网站托管：https://docs.cloudbase.net/hosting/quick-start
- Vue 3 + TypeScript：https://vuejs.org/guide/typescript/overview
- Vue/Vite 快速开始：https://vuejs.org/guide/quick-start.html
- Node.js 版本状态：https://nodejs.org/en/about/previous-releases
