# 开发与联调排错

本文件保留仍适用于当前工程的兼容性和排错知识，不记录逐次修复过程或历史测试次数。
安装和运行命令见 [贡献指南](../../CONTRIBUTING.md)。

## 依赖安装与类型检查

- 后端要求 Python 3.14，使用 uv 按 `backend/.python-version` 准备解释器和环境。自动下载不可用时使用 `uv python install 3.14.7` 或准备匹配的本地解释器；不要修改项目版本约束来绕过安装错误。
- 后台当前 TypeScript 与 `@typescript-eslint/parser` 的 peer 声明不匹配，使用 `npm ci --legacy-peer-deps` 安装现有锁文件。
- 当前 `vue-tsc` 与 TypeScript 组合存在兼容限制；后台 `typecheck` 使用 `tsc`，并未证明 Vue 模板类型正确。
- 后台 `lint` 脚本当前只检查 ESLint 配置。升级兼容工具链与恢复源码检查属于独立改动，不通过修改脚本名称伪装覆盖范围。
- Vite 运行包和 `create-vite` 脚手架的版本号彼此独立；现有工程不需要重新生成脚手架。

## 配置就绪与云端连接

- `CLOUDBASE_ENV_ID` 要与登记的演示或授权 ID 及 `DEMO_MODE` 匹配；相同环境 ID、模式冲突、空值和未替换占位符会被拒绝或判为未配置。
- CloudBase 控制台注入变量名为 `CLOUDBASE_APIKEY`；后端同时兼容模板使用的 `CLOUDBASE_API_KEY`。值仅保存在平台或被 Git 忽略的私有配置中。
- 当前仓储使用 NoSQL REST API 与 Bearer 鉴权，不恢复旧模拟路径或模拟鉴权头。
- `/api/v2/health` 返回 `status=ok` 只说明配置就绪，不证明数据库、微信、学校或 DeepSeek 已真实连通。
- AI Key 是可选配置。未启用或调用失败时，固定结果与核心服务继续使用既有回退。

配置字段见 [环境配置](CONFIGURATION_REGISTRY.md)，初始化与环境登记见
[CloudBase 部署](deploy/CLOUDBASE.md)。

## 小程序与后台联调

- 本地回环 API 仅在微信开发者工具中启用；正式微信客户端使用 AppID 对应的 HTTPS 部署配置。
- 未核验用户可在「我的」重新进入核验；退出登录撤销服务端会话并清除本机状态。不要靠修改本地身份字段恢复权限。
- 小程序 AppID、运行环境与 API 来源要对应；测试号、演示合成身份不能作为正式授权身份。
- 后台 API 基址已经含 `/api/v2`，请求路径不能再次追加该前缀；生产构建显式配置匹配的 HTTPS API 来源。
- 后台静态托管需要深层路由回退到 `/index.html`，后端同时配置对应 CORS 来源和允许请求头。
- 树洞的 AI 初筛不会自动公开内容；后台人工审核决定才会更新关联帖子或回应状态。

## 本地运行的限制

当前仓库不提供独立的合成数据演示入口。未配置 CloudBase 持久化时使用内存仓储，
停止进程后记录不保留。页面数据自动化超时还需区分开发者工具和基础库兼容性，
不能只用静态截图判断功能已正常运行。
