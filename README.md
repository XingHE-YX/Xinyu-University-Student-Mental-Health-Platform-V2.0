# 心语大学生心理健康平台 V2

心语是面向大学生的心理健康自助观察与匿名轻社区项目，包括微信小程序学生端、
独立 Web 管理后台，以及共享的 Python 业务后端。

学生端围绕「今日、自测、树洞、我的」组织功能；后台负责内容审核、安全支持任务、
身份授权与审计。自测提供固定规则的观察结果，AI 只承担受限的辅助说明和内容初筛，
不用于医疗诊断、治疗或替代现实中的危机处置。

## 项目组成

| 目录 | 内容 |
| --- | --- |
| `miniprogram/` | 原生微信小程序，源码位于 `src/`，分类测试位于 `tests/` |
| `admin/` | Vue 3 / TypeScript / Vite 桌面管理后台 |
| `backend/` | Python 3.14 / FastAPI 业务 API、规则、仓储与集成 |
| `docs/` | 产品、详细设计、开发、计划和软著材料 |

## 开始使用

1. 按 [贡献指南](CONTRIBUTING.md) 准备 uv、just、Node.js 和 npm，运行 `just init` 安装后端、小程序和管理后台依赖。
2. 在两个终端分别执行 `just run backend`、`just run admin`；缺少环境配置时服务保持未配置状态。
3. 使用微信开发者工具打开 `miniprogram/`；管理后台和业务后端分别运行，不能把后台当作小程序页面。
4. 联网部署前阅读 [环境配置](docs/develop/CONFIGURATION_REGISTRY.md) 和 [CloudBase 部署](docs/develop/deploy/CLOUDBASE.md)。

仓库中的实现、配置模板与历史材料不等于当前线上服务可用。正式环境仍需完成学校授权、
真实身份接口、支持资源、隐私与专业核验；演示身份和占位资源不能作为正式服务使用。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [DESIGN.md](DESIGN.md) | 系统架构、模块边界和主要数据流 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 安装、运行、检查和贡献说明 |
| [AGENT.md](AGENT.md) | 基本技术栈、文档位置与工具链速查 |
| [产品需求](docs/product/PRD.md) / [产品决策](docs/product/V2_CONFIRMED_PRODUCT_DECISIONS.md) | 功能范围、角色、隐私与产品约定 |
| [应用流程](docs/design/APP_FLOW.md) | 学生端与后台页面、状态和导航 |
| [技术栈](docs/develop/TECH_STACK.md) / [后台开发](docs/develop/ADMIN.md) | 依赖、运行单元与后台目录 |
| [学生端开发](docs/develop/MINIPROGRAM.md) | 小程序目录、样式归属、错误、开发审计及测试 |
| [前端规范](docs/develop/FRONTEND_GUIDELINES.md) / [后端规范](docs/develop/BACKEND_STRUCTURE.md) | 视觉组件、数据库、API 与权限 |
| [AI 接口](docs/develop/V2_AI_INTERFACE_AND_PROMPT_SPEC.md) | 输入边界、提示词、输出与回退 |
| [排错](docs/develop/TROUBLESHOOTING.md) | 安装兼容性、配置与联调问题 |
| [后续实施计划](docs/plans/IMPLEMENTATION_PLAN.md) | 外部依赖、正式发布准备与维护事项 |

短句来源和量表依据位于 `docs/product/`；项目计划书位于 `docs/plans/`；
Word、PDF、截图和源程序归档等软著材料位于 `docs/copyright/`。
