# 贡献指南

## 开发环境

从项目根目录开始，准备以下工具：

| 工具 | 项目要求 |
| --- | --- |
| Node.js | `22.21.0`，见 `.nvmrc` |
| npm | `10.9.4`，见 `admin/package.json` 和 `miniprogram/package.json` |
| Python | 3.11，`backend/pyproject.toml` 要求 `>=3.11,<3.12` |
| 微信开发者工具 | 小程序预览、真机调试与上传 |

依赖以各模块的清单和锁文件为准；本仓库没有根目录统一的 npm 安装入口。
工具链兼容性说明见 [排错文档](docs/develop/TROUBLESHOOTING.md)。

## 安装依赖

后端在项目根目录执行：

```bash
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock
```

管理后台：

```bash
cd admin
npm ci --legacy-peer-deps
```

小程序：

```bash
cd miniprogram
npm ci
```

后台的 `--legacy-peer-deps` 用于现有 TypeScript 与 ESLint 解析器的 peer 声明不匹配。
不要把安装成功理解为 Vue 模板类型检查或全量源码 lint 已完成。

## 运行项目

无需云凭据的界面演示见 [本地演示](docs/develop/deploy/LOCAL.md)。安装依赖后，
在项目根目录的两个终端分别运行：

```bash
backend/.venv/bin/python deploy/local/backend_demo.py
```

```bash
node deploy/local/admin_preview.mjs
```

该入口只使用合成身份、内存仓储和演示任务，不连接真实学校、CloudBase 数据库或 AI。
微信开发者工具打开 `miniprogram/`；本地预览配置只在开发者工具环境生效。

开发真实后端功能时，可在 `backend/` 运行 `.venv/bin/python -m uvicorn app.main:app --reload`。
后台开发服务在 `admin/` 运行 `npm run dev`。对应 API、CORS 和环境配置见
[环境配置](docs/develop/CONFIGURATION_REGISTRY.md) 和 [后台部署](docs/develop/deploy/ADMIN.md)。
缺少配置的服务会保持未配置或降级状态，不应使用默认真实凭据绕过校验。

## 检查改动

后端，在 `backend/` 执行：

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy
```

管理后台，在 `admin/` 执行：

```bash
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
```

小程序，在 `miniprogram/` 执行：

```bash
npm run typecheck
npm run test:structure
```

提交前在项目根目录检查 `git diff --check`。从与改动相关的检查开始，再按影响范围补充其他检查。
现有后台 `typecheck` 使用 `tsc`，不覆盖 Vue 模板；`lint` 只检查 `eslint.config.js`，
不代表全量源码检查。自动测试或构建也不能替代微信真机、浏览器及真实授权环境验证。

## 代码与文档

- 先了解 [系统设计](DESIGN.md)，再阅读相关专题文档；修改范围围绕实际需求。
- API 路由变更同步维护 [后端规范](docs/develop/BACKEND_STRUCTURE.md)；`backend/tests/test_api_contract_registry.py` 会读取其中的路由标题。
- 依赖调整同步维护模块清单、锁文件和 [技术栈](docs/develop/TECH_STACK.md)。
- 配置、权限和 AI 边界变更同步维护对应开发文档；页面状态变更同步维护 [应用流程](docs/design/APP_FLOW.md)。
- 真实密钥、账号密码、身份信息和环境私有配置不进入 Git；合成演示数据不能冒充真实用户或学校资源。
- `docs/plans/` 存放计划，`docs/copyright/` 存放历史交付材料；历史截图、源码快照和 PDF 不作为当前线上验证证据。

提交说明采用 Conventional Commit，例如 `docs: reorganize project documentation` 或
`fix(backend): correct API contract path`。说明实际改动和验证情况，不把未执行的检查记为通过。
