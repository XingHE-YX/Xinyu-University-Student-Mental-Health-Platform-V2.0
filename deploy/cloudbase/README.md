# CloudBase 环境初始化（阶段 7.1）

`environment.template.yaml` 是不含真实值的部署模板。它描述演示和真实授权环境必须分别创建的 EnvID、数据库命名空间、Python 3.11 HTTP 云函数和静态网站托管入口。模板中的 `${...}` 只能在 CloudBase 控制台、密钥管理或被 Git 忽略的本地渲染中替换。

## 初始化顺序

1. 创建两个不同的 CloudBase 环境，并登记 EnvID；不得把一个环境同时标为演示和授权。
2. 在每个环境创建独立数据库命名空间，并按 `BACKEND_STRUCTURE.md` 第 4 节建立集合、索引和唯一约束。不要由小程序启动时创建集合。
3. 上传包含 `backend/scf_bootstrap` 和 `backend/requirements.lock` 对应依赖的 Python 3.11 HTTP 函数，监听 9000 端口。函数名称和变量按模板分别配置。
4. 只在函数的加密环境变量或 CloudBase 密钥管理中填写 API Key、微信密钥、后台会话秘密和密码哈希；不要写入小程序、`admin/dist`、日志或 Git 跟踪文件。
5. 构建 `admin/dist` 后分别发布到两个环境的静态网站托管，配置 HTTPS 根来源（不能带路径）、SPA fallback `/index.html`，并将来源加入后端 CORS/会话允许列表。
6. 发布前使用后端 `validate_deployment_config` 检查 EnvID、命名空间和来源；先访问 `/api/v1/health`，再执行接口契约测试。

## 必须保留的隔离证据

- 演示和授权 EnvID、命名空间、函数变量、托管来源逐项不同；
- 演示重置仅在服务端确认 `demo` 时可用，授权环境直接拒绝；
- 未配置或授权未完成时保持 `unconfigured`，不使用默认凭据或虚构支持资源；
- 数据库索引清单与 `BACKEND_STRUCTURE.md` 一致，且两个环境分别执行；
- 小程序只调用 Python 业务 API，后台构建产物不进入小程序包。
