# 心语 V2 项目参考

## 基本技术栈

| 模块 | 技术 | 目录 |
| --- | --- | --- |
| 学生端 | 原生微信小程序、TypeScript、WXML、WXSS | `miniprogram/` |
| 管理后台 | Vue 3、TypeScript、Vite、Vue Router、Pinia | `admin/` |
| 业务后端 | Python 3.11、FastAPI、Pydantic、HTTPX、Uvicorn | `backend/` |
| 数据与部署 | CloudBase 文档型数据库、Python HTTP 云函数、静态网站托管 | `docs/develop/deploy/` |
| AI 接口 | 后端调用 DeepSeek Chat Completions | `backend/app/integrations/` |

## 文档内容

| 位置 | 内容 |
| --- | --- |
| [README.md](README.md) | 项目介绍、目录与文档导航 |
| [DESIGN.md](DESIGN.md) | 架构、模块职责、数据流与系统边界 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 环境搭建、运行、检查与贡献说明 |
| `docs/product/` | 产品需求、确认决策、每日短句与量表依据 |
| `docs/design/` | 学生端与后台的页面、状态和应用流程 |
| `docs/develop/` | 技术栈、前后端规范、配置、AI 接口与排错 |
| `docs/develop/deploy/` | CloudBase、后端、后台与小程序部署要求 |
| `docs/plans/` | 后续实施计划与项目计划书 |
| `docs/copyright/` | 软著申请、源程序和软件使用说明材料 |

## 工具链

| 工具 | 用途与版本来源 |
| --- | --- |
| Node.js | `22.21.0`，见 `.nvmrc` |
| npm | `10.9.4`，见两个前端的 `package.json`；依赖由锁文件记录 |
| Python | `>=3.11,<3.12`，见 `backend/pyproject.toml` |
| uv | 管理 Python、`backend/.venv` 与依赖；清单为 `pyproject.toml`，锁文件为 `uv.lock` |
| 微信开发者工具 | 小程序预览、真机调试与上传 |
| TypeScript、Vite | 前端类型检查与后台构建 |
| Vitest、Node test runner | 后台与小程序测试 |
| pytest、Ruff、mypy | 后端测试、格式、静态检查与类型检查 |
| ESLint、Prettier | 后台现有 lint 与格式检查 |
| Git | 版本管理 |

安装和检查命令见 [CONTRIBUTING.md](CONTRIBUTING.md)，完整依赖清单见
[技术栈文档](docs/develop/TECH_STACK.md)。
