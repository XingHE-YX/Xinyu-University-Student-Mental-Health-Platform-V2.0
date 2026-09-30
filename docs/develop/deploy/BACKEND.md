# Python 云函数发布

仓库不提供云函数打包脚本或启动文件。发布时需按 CloudBase Python 3.11 HTTP
函数规范另行准备应用、锁定依赖和平台要求的 `scf_bootstrap`，监听 `0.0.0.0:9000`。
不要把 `.env`、密钥文件或测试夹具放入产物。

## 构建

运行依赖以 `backend/pyproject.toml` 和 `backend/uv.lock` 为准，可在 `backend/`
使用 `uv export --locked --no-dev --no-emit-project --format requirements-txt` 导出供发布使用。
依赖需兼容目标运行时和平台，不能直接上传本机虚拟环境。
将另行准备并验证的函数包上传到 CloudBase 的 Python 3.11 HTTP
函数入口，并在控制台配置 `scf_bootstrap`、9000 端口和对应环境变量。演示与
真实授权环境必须分别构建/上传或分别绑定函数配置；不要把授权环境变量复制到
演示函数。

## 健康检查和接口契约

健康检查必须先于契约测试：

```text
backend/.venv/bin/python backend/scripts/verify_health_then_contract.py \
  --url https://<api-origin> --contract backend/.venv/bin/pytest
```

脚本只显示 HTTP 状态和服务状态，不输出响应正文、请求体或环境变量。未配置的
本地服务可使用 `--allow-degraded` 做冒烟检查；演示/授权发布验收不应放宽为
`degraded`。

## 服务端变量

变量名和演示/授权分离规则见 `docs/develop/CONFIGURATION_REGISTRY.md`。
API Key、微信密钥、后台密码哈希
和会话秘密只能在 CloudBase 加密环境变量或密钥管理中填写，不能写进压缩包、日志
或 Git 跟踪文件。
