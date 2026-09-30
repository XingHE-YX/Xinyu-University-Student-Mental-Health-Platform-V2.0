# 贡献指南

## 开发环境

从项目根目录开始，准备以下工具：

| 工具 | 项目要求 |
| --- | --- |
| Node.js | `22.21.0`，见 `.nvmrc` |
| npm | `10.9.4`，见 `admin/package.json` 和 `miniprogram/package.json` |
| Python | 3.14，`backend/pyproject.toml` 要求 `>=3.14,<3.15` |
| uv | Python 版本、虚拟环境、依赖与锁文件管理 |
| just | 根目录 `Justfile` 的开发命令编排 |
| 微信开发者工具 | 小程序预览、真机调试与上传 |

依赖以各模块的清单和锁文件为准；在根目录运行 `just init` 统一安装三个模块的依赖。
工具链兼容性说明见 [排错文档](docs/develop/TROUBLESHOOTING.md)。

## 根目录快捷命令

安装 uv 和 just 后，在项目根目录执行 `just` 查看命令：

| 命令 | 用途 |
| --- | --- |
| `just venv` | 仅创建 `backend/.venv`，不安装依赖；环境已存在时使用 `just init` |
| `just init` | 按锁文件安装后端、小程序和管理后台的运行与开发依赖，创建或同步后端环境 |
| `just run backend` | 启动后端开发服务，开启 reload，默认 `127.0.0.1:9000` |
| `just run admin` | 启动管理后台 Vite 服务，需先执行 `just init` |
| `just check backend` | Ruff、格式和 mypy 检查；省略 backend 效果相同 |
| `just test backend` | 后端 pytest；省略 backend 效果相同 |

首次使用若 uv 禁止自动下载解释器，先执行 `uv python install 3.14.7`。
后端地址可以通过 `BACKEND_HOST`、`BACKEND_PORT` 覆盖，例如
`BACKEND_PORT=9001 just run backend`。未知模块会返回错误，不启动服务。
uv 命令不需要激活环境；需要交互使用时，在当前 shell 执行
`source backend/.venv/bin/activate`。`just venv` 无法激活调用它的父 shell。

## 安装依赖

在项目根目录统一安装：

```bash
just init
```

该命令依次同步后端环境、安装小程序和管理后台的 npm 依赖；任一步骤失败都会停止。
也可以按模块单独安装。后端在项目根目录执行：

```bash
uv python install 3.14.7
uv sync --project backend --locked
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

安装依赖后，在项目根目录的两个终端分别运行：

```bash
cd backend
uv run --locked python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 9000
```

```bash
cd admin
npm run dev
```

当前仓库不提供预置合成身份和演示任务的本地演示入口。
微信开发者工具打开 `miniprogram/`，项目配置指定源码根目录为 `src/`；
本地预览配置位于 `src/infra/config/local-preview.ts`，只在开发者工具环境生效。
小程序目录、错误、日志与测试规范见 [学生端开发](docs/develop/MINIPROGRAM.md)。

对应 API、CORS 和环境配置见
[环境配置](docs/develop/CONFIGURATION_REGISTRY.md) 和 [后台部署](docs/develop/deploy/ADMIN.md)。
缺少配置的服务会保持未配置或降级状态，不应使用默认真实凭据绕过校验。

## 检查改动

后端，在 `backend/` 执行：

```bash
uv run --locked python -m pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
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
npm test
```

可用 `npm run test:ui`、`npm run test:business`、`npm run test:utils` 分别执行
页面与组件、业务、工具测试；`npm run test:structure` 只执行目录、页面与样式结构检查。
测试代码使用 `tests/helpers/` 的微信 mock，不连接真实业务服务。

提交前在项目根目录检查 `git diff --check`。从与改动相关的检查开始，再按影响范围补充其他检查。
现有后台 `typecheck` 使用 `tsc`，不覆盖 Vue 模板；`lint` 只检查 `eslint.config.js`，
不代表全量源码检查。自动测试或构建也不能替代微信真机、浏览器及真实授权环境验证。

## 代码与文档

后端运行依赖统一声明在 `backend/pyproject.toml` 的 `project.dependencies`，
开发工具声明在 `dependency-groups.dev`，传递依赖锁定在提交的 `backend/uv.lock`。
虚拟环境位于 `backend/.venv`；uv 会按 `.python-version` 选择 Python 3.14.7，
缺少解释器时可由 uv 下载。同步默认包含开发依赖，运行环境使用 `uv sync --no-dev --locked`。
在 `backend/` 使用 `uv add <package>` 或 `uv add --dev <package>` 添加依赖，
修改清单后执行 `uv lock` 并同时提交清单和锁文件。不要手工维护 requirements 文件。

- 先了解 [系统设计](DESIGN.md)，再阅读相关专题文档；修改范围围绕实际需求。
- API 路由变更同步维护 [后端规范](docs/develop/BACKEND_STRUCTURE.md)；`backend/tests/contracts/test_api_contract_registry.py` 会读取其中的路由标题。
- 依赖调整同步维护模块清单、锁文件和 [技术栈](docs/develop/TECH_STACK.md)。
- 配置、权限和 AI 边界变更同步维护对应开发文档；页面状态变更同步维护 [应用流程](docs/design/APP_FLOW.md)。
- 真实密钥、账号密码、身份信息和环境私有配置不进入 Git；合成演示数据不能冒充真实用户或学校资源。
- `docs/plans/` 存放计划，`docs/copyright/` 存放历史交付材料；历史截图、源码快照和 PDF 不作为当前线上验证证据。

提交说明采用 Conventional Commit，例如 `docs: reorganize project documentation` 或
`fix(backend): correct API contract path`。说明实际改动和验证情况，不把未执行的检查记为通过。
