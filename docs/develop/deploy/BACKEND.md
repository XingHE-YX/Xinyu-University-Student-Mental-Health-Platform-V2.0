# Python 3.14 后端发布

后端要求 `>=3.14,<3.15`，本地和容器基线为 Python 3.14.7。仓库提供
`backend/Dockerfile`，以容器作为发布入口。目标平台必须支持该镜像和 HTTPS
转发；本文不假定 CloudBase 的托管 Python 云函数运行时支持 3.14。
选用自定义运行时前，应另行验证解释器、依赖和平台启动协议。

## 构建与运行

在仓库根目录构建：

```sh
docker build -t xinyu-backend:local backend
docker run --rm --name xinyu-backend -p 9000:9000 \
  --env-file backend/.env.demo.local xinyu-backend:local
```

Dockerfile 使用多阶段构建，以 `uv sync --frozen --no-dev --no-editable` 安装锁定的
生产依赖。运行层使用非 root UID 10001，启动 `app.main:app` 并监听
`0.0.0.0:9000`。`.dockerignore` 排除环境文件、虚拟环境、测试和密钥文件。
不要上传本机 `.venv`，不要把秘密放进构建参数或镜像层。

演示与授权部署分别注入各自配置，持久化部署显式设置 `PERSISTENCE_BACKEND=cloudbase`。
反向代理保留 `/api/v2` 路径和请求编号，配置 HTTPS、后台允许来源、访问控制、
资源限制及优雅关闭。密码默认单次使用 64 MiB，工作线程并发上限为 2；
容器内存须覆盖并发密码操作与应用开销，部署前实测并发延迟和内存峰值。

容器健康检查访问 `/api/v2/health`，仅用于确认 HTTP 进程能响应；
该接口的 `status=ok` 表示配置就绪，不证明外部服务连通。
镜像构建、平台部署和真实 CloudBase 事务必须在目标环境单独验收。

## 健康检查和接口契约

健康检查先于契约测试，在仓库根目录执行：

```sh
backend/.venv/bin/python backend/scripts/verify_health_then_contract.py \
  --url https://<api-origin> --contract backend/.venv/bin/pytest
```

脚本只显示 HTTP 状态和服务状态。未配置的本地服务可使用 `--allow-degraded`
做冒烟检查；演示与授权发布验收不放宽为 `degraded`。

## 密码与客户端迁移

新密码哈希只生成 Argon2id，旧 PBKDF2-SHA256 仍可验证。当前管理员没有密码注册
接口；使用 `scripts.reset_demo_admin_password` 在受控本地配置中重置密码，工具通过
隐藏输入读取密码。按 `--help` 指定本地文件，禁止把明文密码写入命令行或日志。
部署更新 `ADMIN_PASSWORD_HASH` 后，旧管理员会话在验证或刷新时失效。

业务路由已统一为 `/api/v2`，没有 `/api/v1` 兼容别名。小程序 `API_BASE_URL`
和后台 `VITE_API_BASE_URL` 必须同步使用该前缀，并重新构建发布。
先在独立演示环境完成登录、心情、自测、树洞、后台任务和审计验证，再协调
后端与两端发布窗口；已发布旧小程序需要更新。回退时恢复整套旧后端和客户端
配置，并核对新增可选会话字段与已有数据，不单独回退某一端。

## 服务端变量

变量和环境隔离规则见 [配置登记](../CONFIGURATION_REGISTRY.md)。
API Key、微信密钥、密码哈希和会话秘密只通过运行时环境或密钥管理注入。
配置主体位于 Python 代码，Pydantic 校验后形成不可变设置；应用不读取 TOML。
