# 管理后台开发

心语管理后台是独立桌面 Web 应用，使用 Vue 3、TypeScript 和 Vite。
后台不进入微信小程序导航，基准画布为 1440×900，并支持窄桌面窗口下的响应式布局。

## 目录

| 项目根目录下的位置 | 内容 |
| --- | --- |
| `admin/src/views/` | 登录、工作台、详情、异常和审计页面 |
| `admin/src/components/` | 共享状态、任务、表格与操作组件 |
| `admin/src/services/` | 业务 API 客户端 |
| `admin/src/stores/` | 会话与页面状态 |
| `admin/src/config/` | 运行环境与 API 配置 |
| `admin/src/styles/` | 设计令牌和基础样式 |

安装、运行与检查命令见 [贡献指南](../../CONTRIBUTING.md)。
本地开发启动见 [贡献指南](../../CONTRIBUTING.md)，生产 API 配置与托管见
[后台部署](deploy/ADMIN.md)。

依赖见 [技术栈](TECH_STACK.md)，视觉、组件和尺寸约定见
[前端规范](FRONTEND_GUIDELINES.md)，页面与权限状态见 [应用流程](../design/APP_FLOW.md)。
