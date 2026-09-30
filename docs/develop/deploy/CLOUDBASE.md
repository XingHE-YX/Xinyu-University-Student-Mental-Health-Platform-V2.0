# CloudBase 环境初始化

演示和真实授权环境必须分别创建 EnvID、数据库命名空间、Python 3.11 HTTP 云函数和静态网站托管入口。仓库不提供部署模板；实际配置只在 CloudBase 控制台、密钥管理或被 Git 忽略的本地文件中填写。

## 初始化顺序

1. 创建两个不同的 CloudBase 环境，并登记 EnvID；不得把一个环境同时标为演示和授权。
2. 在每个环境创建独立数据库命名空间，并按 `docs/develop/BACKEND_STRUCTURE.md` 第 4 节建立集合、索引和唯一约束。不要由小程序启动时创建集合。
3. 按平台规范另行准备 Python 3.11 HTTP 函数包及启动文件，监听 9000 端口。仓库不提供函数打包工具，函数名称和变量按环境分别配置。
4. 只在函数的加密环境变量或 CloudBase 密钥管理中填写 API Key、微信密钥、后台会话秘密和密码哈希；不要写入小程序、`admin/dist`、日志或 Git 跟踪文件。
5. 构建 `admin/dist` 后分别发布到两个环境的静态网站托管，配置 HTTPS 根来源（不能带路径）、SPA fallback `/index.html`，并将来源加入后端 CORS/会话允许列表。
6. 发布前使用后端 `validate_deployment_config` 检查 EnvID、命名空间和来源；先访问 `/api/v1/health`，再执行接口契约测试。

当前文档型数据库使用官方 NoSQL REST API：
`https://<env-id>.api.tcloudbasegateway.com/v1/database/instances/(default)/databases/(default)`，
服务端 API Key 通过 `Authorization: Bearer` 发送。不要恢复旧的 `/api/v2/.../documents:find`
模拟路径或 `X-CloudBase-Authorization` 请求头。

CloudBase 控制台的“API Key 设置”会以 `CLOUDBASE_APIKEY` 注入所选 Key；后端兼容
这个平台变量名以及 `CLOUDBASE_API_KEY`。优先使用控制台托管注入，
不要把 Key 明文添加到普通环境变量。

演示环境私有配置准备完成后，在 `backend/` 目录初始化：

```text
uv run --locked python -m scripts.initialize_cloudbase .env.demo.local
```

命令可安全重跑：已有集合、索引和相同 `_id` 的冻结种子会被识别并保留；它不会显示密钥。

## 运行时环境登记

每个函数都需要设置当前 `CLOUDBASE_ENV_ID`，以及已登记的
`CLOUDBASE_ENV_ID_DEMO`、`CLOUDBASE_ENV_ID_AUTHORIZED`。后端启动时会读取后两项，
核对当前 ID 与 `DEMO_MODE`；不能只设置当前 ID 和模式就认为环境已授权。
两项登记值相同或当前模式与已登记的环境相反时，启动会拒绝该配置。

按步骤先建设演示环境时，可以省略尚未创建的 `CLOUDBASE_ENV_ID_AUTHORIZED`。
正式发布前再补齐两套不同 ID；不要填入虚构 ID。空白值和未替换的 `${...}`
占位符不会通过配置就绪判定。

运行时变量统一叫 `WECHAT_APPSECRET`，环境对应密钥引用为
`WECHAT_APPSECRET_DEMO` / `WECHAT_APPSECRET_AUTHORIZED`。
`ADMIN_SESSION_SECRET` 也必须分别配置。`WECHAT_APPID` 是非秘密环境值，无需作为密钥引用。

`DEEPSEEK_API_KEY` 是可选项；暂不接入 AI 时，直接省略该变量。
必需密钥与可选 DeepSeek 密钥应分别在平台登记，并检查对应环境的密钥是否已创建。
核心配置齐全时，缺少 AI Key 不阻断登录和固定规则流程，AI 调用使用已有回退。

`/api/v1/health` 的 `status=ok` 当前仅表明配置就绪，并未探测 CloudBase、微信、
学校或 DeepSeek 的真实连通性。数据库持久化与真实接口仍需在后续步骤逐项验收。

## 环境隔离

- 演示和授权 EnvID、命名空间、函数变量、托管来源逐项不同；
- 演示重置仅在服务端确认 `demo` 时可用，授权环境直接拒绝；
- 未配置或授权未完成时保持 `unconfigured`，不使用默认凭据或虚构支持资源；
- 数据库索引清单与 `docs/develop/BACKEND_STRUCTURE.md` 一致，且两个环境分别执行；
- 小程序只调用 Python 业务 API，后台构建产物不进入小程序包。
