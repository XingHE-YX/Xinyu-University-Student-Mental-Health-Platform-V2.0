# 心语 V2 环境配置登记表

## 0. 文档信息

- 文档版本：CONFIG-1.0
- 登记日期：2026-08-28
- 适用范围：微信小程序、Python 业务后端、独立桌面 Web 管理后台
- 部署说明：`docs/develop/deploy/`；后续工作：`docs/plans/IMPLEMENTATION_PLAN.md`
- 状态说明：仓库保留演示环境接入与正式环境配置位；实时状态由实际配置和服务端判定，本表不作为当前线上验证记录

本文件只登记配置位、状态和存放规则，不保存任何真实密钥、密码、身份信息、学校联系人或真实支持资源。真实值由用户在相应环境的安全配置中填写；填写后应同步维护本表的状态，不把真实值回填到 Git 跟踪文件。

## 1. 三种环境状态

每一个配置位必须明确处于以下三种状态之一：

| 状态           | 定义                                                     | 允许行为                                                                     |
| -------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `demo`         | 使用独立演示环境、合成数据和演示资源的配置已完成         | 可以进行受控演示、演示任务流和演示数据重置；不得读取真实数据                 |
| `authorized`   | 使用经过学校、隐私和资源授权的真实环境配置已完成         | 只允许已授权的真实功能；禁止演示重置，必须继续遵守最小必要暴露和审计规则     |
| `unconfigured` | 配置缺失、格式不合法、授权尚未完成或环境无法被服务端确认 | 不得伪造可用；相关功能显示未配置、不可用或回退状态，不创建需要真实授权的记录 |

状态由服务端根据环境标识、配置完整性和授权开关判定。前端显示的“演示模式”不能替代服务端的环境校验；`DEMO_MODE` 不能单独作为数据隔离依据。

## 2. 配置登记矩阵

表格中的 `${...}` 是占位符，不是可用值。带“秘密”标记的配置只能保存为云函数加密环境变量或 CloudBase 密钥管理引用。

| 配置位                                          | 运行单元               | `demo` 值或引用                                         | `authorized` 值或引用                          | `unconfigured` 状态与行为                                                          | 秘密/存放规则                                                                    |
| ----------------------------------------------- | ---------------------- | ------------------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| 微信小程序 AppID `WECHAT_MINIPROGRAM_APPID`     | 小程序构建             | `${WECHAT_MINIPROGRAM_APPID_DEMO}`                      | `${WECHAT_MINIPROGRAM_APPID_AUTHORIZED}`       | 空值或未登记；开发者工具不能以真实发布配置启动                                     | AppID 不是 API 密钥，但必须按环境分离；不写进业务页面                            |
| 微信服务端 AppID `WECHAT_APPID`                 | Python 后端            | `${WECHAT_APPID_DEMO}`                                  | `${WECHAT_APPID_AUTHORIZED}`                   | 微信登录交换返回未配置；不伪造登录成功                                             | 服务端环境配置；不得进入前端包、日志或错误消息                                   |
| 微信服务端密钥 `WECHAT_APPSECRET`               | Python 后端            | `${WECHAT_APPSECRET_DEMO}`                              | `${WECHAT_APPSECRET_AUTHORIZED}`               | 登录交换不可用；保持未登录状态                                                     | 秘密；只存服务端密钥管理                                                         |
| 演示 CloudBase 环境 ID `CLOUDBASE_ENV_ID`       | Python 后端/小程序配置 | `${CLOUDBASE_ENV_ID_DEMO}`                              | 不适用                                         | 缺失或不匹配；服务端拒绝启动对应环境                                               | 环境级配置；不能只依赖 `DEMO_MODE`                                               |
| 真实授权 CloudBase 环境 ID `CLOUDBASE_ENV_ID`   | Python 后端/小程序配置 | 不适用                                                  | `${CLOUDBASE_ENV_ID_AUTHORIZED}`               | 缺失或不匹配；真实授权能力保持关闭                                                 | 环境级配置；与演示 Env ID、数据库和命名空间分离                                  |
| CloudBase HTTP 访问凭据 `CLOUDBASE_API_KEY`     | Python 后端            | `${CLOUDBASE_API_KEY_DEMO}`                             | `${CLOUDBASE_API_KEY_AUTHORIZED}`              | 数据库访问显示服务未配置；不回退到前端直连                                         | 秘密；只存服务端密钥管理                                                         |
| 学生端业务 API 地址 `API_BASE_URL`              | 小程序                 | `https://<demo-api-origin>/api/v1`                      | `https://<authorized-api-origin>/api/v1`       | 空值、非 HTTPS 或未登记；请求功能显示未配置                                        | 非秘密环境配置；不得散落在页面代码中                                             |
| 后台业务 API 地址                               | 独立 Web 后台          | 与演示 `API_BASE_URL` 共用同一 Python 后端地址          | 与授权 `API_BASE_URL` 共用同一 Python 后端地址 | 未登记；后台显示服务未配置，不加载受保护事实                                       | 当前架构要求学生端与后台使用同一后端能力边界；若未来分离地址，必须先更新技术规范 |
| 后台 Web 来源 `ADMIN_WEB_ORIGIN`                | 独立 Web 后台          | `https://<demo-admin-origin>`                           | `https://<authorized-admin-origin>`            | 空值或非 HTTPS；后台不认为来源已授权                                               | 非秘密环境配置；必须与后端 CORS/会话来源配置一致                                 |
| DeepSeek API Key `DEEPSEEK_API_KEY`             | Python 后端            | `${DEEPSEEK_API_KEY_DEMO}`                              | `${DEEPSEEK_API_KEY_AUTHORIZED}`               | AI 辅助直接进入固定回退；评分、安全分支和人工流程继续可用                          | 秘密；只存服务端加密环境变量或密钥管理，不写入请求日志                           |
| 学校身份核验地址 `SCHOOL_IDENTITY_PROVIDER_URL` | Python 后端            | `${SCHOOL_IDENTITY_PROVIDER_URL_DEMO}` 或合成演示适配器 | `${SCHOOL_IDENTITY_PROVIDER_URL_AUTHORIZED}`   | 身份核验显示未配置；不得伪造核验成功，不进入需要身份的私密动作                     | 地址本身可为非秘密，但服务凭据仍按秘密管理                                       |
| 校内和紧急支持资源                              | Python 后端配置/数据库 | 合成演示资源，明确标注演示模式                          | `${AUTHORIZED_SUPPORT_RESOURCE_SET}`，须经核验 | 显示“校内支持信息尚未配置”及已核验的现实替代方式；不得虚构联系人、电话、时段或承诺 | 资源内容按环境隔离；真实联系人不能进入 Git 或演示数据                            |
| 支持资源版本 `SUPPORT_RESOURCE_VERSION`         | Python 后端            | `${SUPPORT_RESOURCE_VERSION_DEMO}`                      | `${SUPPORT_RESOURCE_VERSION_AUTHORIZED}`       | 资源接口返回未配置状态，不渲染过期或未知资源                                       | 环境配置；每次变更需可审计                                                       |
| 后台固定登录名                                  | Python 后端/后台       | `心理健康中心工作人员`                                  | `心理健康中心工作人员` 或授权系统映射          | 未配置；后台不得提供自由角色选择来绕过配置                                         | 展示名称不是秘密；能力仍由服务端会话决定                                         |
| 后台能力                                        | Python 后端/后台       | `超级管理员`（仅演示能力投影）                          | 由服务端 capability 配置决定                   | 未配置；不显示受保护任务                                                           | 不能由客户端提交或切换角色                                                       |
| 后台密码哈希 `ADMIN_PASSWORD_HASH`              | Python 后端            | `${ADMIN_PASSWORD_HASH_DEMO}`                           | `${ADMIN_PASSWORD_HASH_AUTHORIZED}`            | 登录失败并显示配置错误；不使用默认密码                                             | 秘密；只保存哈希引用/哈希值于服务端安全配置，不保存明文                          |
| 后台会话秘密 `ADMIN_SESSION_SECRET`             | Python 后端            | `${ADMIN_SESSION_SECRET_DEMO}`                          | `${ADMIN_SESSION_SECRET_AUTHORIZED}`           | 不创建有效后台会话                                                                 | 秘密；只存服务端密钥管理，轮换后撤销旧会话                                       |
| 环境标识 `DEMO_MODE`                            | Python 后端            | `true`，且必须命中演示 Env ID 白名单                    | `false`，且必须命中授权 Env ID 白名单          | 缺失、与 Env ID 不一致或无法确认；拒绝演示重置和受保护环境启动                     | 非秘密开关，但必须由服务端校验，不能由前端决定                                   |

## 3. 配置存放和读取边界

### 3.1 小程序

- 只读取非秘密的环境构建配置：AppID、CloudBase Env ID 和 HTTPS `API_BASE_URL`。
- 不包含 `WECHAT_APPSECRET`、`CLOUDBASE_API_KEY`、`DEEPSEEK_API_KEY`、`ADMIN_PASSWORD_HASH`、`ADMIN_SESSION_SECRET` 或任何真实支持资源秘密。
- 微信开发者工具用于打开项目、选择对应 AppID/环境、预览、真机核验和上传；它不是秘密存储位置。

### 3.2 Python 后端

- 读取服务端环境变量和 CloudBase 密钥管理中的配置。
- 启动时从 `CLOUDBASE_ENV_ID_DEMO` 和 `CLOUDBASE_ENV_ID_AUTHORIZED` 读取已登记的环境 ID，再与当前 `CLOUDBASE_ENV_ID` 和 `DEMO_MODE` 核对。两套 ID 不得相同，不会根据当前模式自动登记目标环境。仅演示环境已创建时，正式环境变量可暂时省略；正式发布前必须补齐。
- 启动时校验环境 ID、`DEMO_MODE`、配置状态和演示重置白名单；不一致时拒绝进入对应状态。
- API 响应只返回必要的环境状态，例如 `demo`、`authorized` 或 `unconfigured`，不返回密钥、密码哈希、连接串或真实环境 ID。
- DeepSeek 固定使用 `https://api.deepseek.com/chat/completions`、请求模型 `deepseek-v4-flash` 和记录版本 `DeepSeek-V4-Flash-0731`；Key 缺失时使用固定回退。
- `DEEPSEEK_API_KEY` 为可选配置。仅缺少该值时，不把核心环境降为 `unconfigured`；数据库、微信、后台会话、身份核验和支持资源配置仍须齐全。环境配置通过不等于外部服务连通或真实数据库持久化已验收。

### 3.3 独立 Web 后台

- 只读取后台 API 返回的会话、能力和环境状态，不把服务端秘密编译进 `admin/dist`。
- `ADMIN_WEB_ORIGIN` 必须使用 HTTPS，并与后端允许的来源、会话和跨域设置一致。
- 窄桌面窗口采用响应式列布局；未配置、无权限、会话过期和冲突状态不得通过隐藏按钮绕过。

## 4. 三端隔离清单

| 检查项   | 必须满足的条件                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------ |
| 环境隔离 | 演示和真实授权使用不同 CloudBase Env ID、数据库命名空间、函数配置、静态托管入口和秘密            |
| 数据隔离 | 演示账号、帖子、回应、答卷、身份、安全任务、工作任务和审计均使用合成数据；演示端不能查询真实对象 |
| 构建隔离 | 小程序包、Python 函数包和后台 `dist` 分别构建；后台不进入小程序包，Python 不由 Node.js 运行      |
| 访问隔离 | 小程序和后台均通过 Python 业务 API；前端不直连 CloudBase 数据库管理接口或 DeepSeek               |
| 日志隔离 | 日志和审计不写密钥、明文密码、令牌、完整答案、未脱敏树洞正文、安全确认原文或模型原始输入输出     |
| 重置隔离 | 只有服务端确认 `demo` 且命中演示白名单时允许重置；`authorized` 环境在执行删除前直接拒绝          |

## 5. 配置维护说明

- 本文登记字段、用途、存放边界和未配置行为，不保存实时连通性结果、云资源账单或逐次部署日志。
- 当前请求模型名与记录版本分别为 `deepseek-v4-flash` 和 `DeepSeek-V4-Flash-0731`；它们对应后端的接口标识与版本记录。
- 私有配置和 CloudBase 控制台中的实际值按各环境独立维护；仓库中的占位符不意味着现有演示服务未配置，也不证明服务当前可用。
- 固定合成身份只用于登记的演示环境；正式授权环境使用学校核验接口。演示支持资源必须明确标记占位，不作为真实联系方式。
- 真实密钥、密码哈希、会话秘密和个人信息不回填本文；状态变更仅记录环境类型、配置引用与核验日期。

## 6. 填写和审查顺序

用户后续填写任何真实值时，必须同时完成：

1. 在对应的演示或授权安全配置中填写值，不直接修改业务页面或提交密钥文件；
2. 将本表对应行的状态更新为 `demo` 或 `authorized`，只记录状态、引用名和核验日期，不记录秘密本身；
3. 运行服务端环境一致性检查，确认 Env ID、数据命名空间、`DEMO_MODE` 和来源配置匹配；
4. 在部署前检查小程序包、`admin/dist`、Python 日志和 Git 跟踪文件没有秘密或真实个人数据；
5. 资源、身份核验和真实响应角色未完成授权前，保持 `unconfigured`，不得用演示资源冒充真实学校支持。
