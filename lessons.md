## 2026-08-28：工程初始化兼容性记录

- `create-vite@8.2.2` 不存在；脚手架工具版本与 `vite` 运行包版本独立，使用可用的 `create-vite@8.2.0` 生成结构，并将项目运行依赖锁定为 `vite@8.2.2`。
- `@typescript-eslint/parser@8.68.0` 的 peer 声明要求 TypeScript 小于 `6.1.0`，而规范锁定 `typescript@7.0.2`；后台安装必须使用 `npm --legacy-peer-deps`，不能擅自替换规范版本。
- `vue-tsc@3.3.11` 在 `typescript@7.0.2` 下无法解析 `typescript/lib/tsc`。初始化阶段保留两者的精确依赖，但 `npm run typecheck` 使用官方 `tsc` 检查 TypeScript 配置，`npm run build` 使用 Vite；未来若需要 Vue 模板类型检查，必须先由用户批准新的版本契约。
- `@typescript-eslint/parser@8.68.0` 在 `typescript@7.0.2` 下会直接拒绝加载（当前只支持 TypeScript 小于 `6.1.0`）；初始化阶段的 `npm run lint` 只检查 ESLint 配置文件，TS/Vue 源码 lint 必须在版本契约解决后恢复。
- 本机没有可直接调用的 Python 3.11；使用临时工具环境安装 Python 3.11.11，并在项目的 `backend/.venv` 中补装 pip 后运行 `pip-tools==7.6.1`。
- `jsdom@30.0.1` 在 Node `22.21.0` 下会发出 engine 警告（要求 `22.22.2` 或更高的 Node 22 补丁版本），后续运行浏览器环境测试时需单独记录实际 Node 版本或经用户批准调整基线。

## 2026-08-28：阶段 0 配置基线记录

- 新增的 `CONFIGURATION_REGISTRY.md` 首次格式检查未通过项目的 Prettier Markdown 规则；已使用项目现有 Prettier 格式化，并在完成声明前重新检查。以后新增 Markdown 配置或规范文件也必须执行格式检查。

## 2026-08-28：阶段 1 精确运行时验证

- 当前默认终端使用 Node `v26.0.0` / npm `11.12.1`，不符合项目锁定的 Node `22.21.0` / npm `10.9.4`；已新增根目录 `.nvmrc` 和两个前端包的 `packageManager` 元数据，并使用 Node 官方 `22.21.0` 临时工具包完成清洁安装和类型检查。以后执行阶段 1 的前端验证必须先确认 `node --version` 与 `npm --version`。
- 清理 Vite 初始模板资源后，后台 `index.html` 仍残留 `vite.svg` 图标引用；已删除无效引用并更新页面语言和标题。以后清理脚手架资源时必须同时检查入口 HTML 的引用。
- 直接执行 `backend/scf_bootstrap` 时因当前终端未激活项目虚拟环境而出现 `python: not found`；启动脚本依赖 CloudBase 或本地 PATH 提供 `python`。本地验证必须先使用 `backend/.venv/bin`（或激活该虚拟环境），不能因此替换 Python 3.11 运行时。

## 2026-08-28：阶段 1 微信开发者工具验证

- 微信开发者工具 `2.01.2510290` 首次加载当前项目时曾出现可重复的内部启动错误：`TypeError: Cannot read property 'getPreCompileOptions' of undefined` 和 `simulator not found`。重新编译后模拟器成功加载，说明命令行类型检查通过后还必须在指定工具中确认实际运行状态。
- 当前项目在工具中使用游客 AppID `touristappid` 和灰度基础库 `3.16.1` 时，控制台会出现 `webapi_getwxaasyncsecinfo:fail`、`timeout` 以及游客模式 API 限制提示；这些是工具游客环境的模拟 API 报错，不是学生端代码编译错误。后续配置真实小程序 AppID 并选择稳定基础库后，需要重新检查控制台。
- 使用临时编译模式把启动页切换到 `pages/today/index` 后，已确认“今日”空状态页可加载，底部“今日 / 自测 / 树洞 / 我的”四项均可切换到对应页面。临时编译模式会生成 `miniprogram/project.private.config.json` 并改写 `project.config.json`；验证后已恢复正式项目配置，并将私有配置加入 `.gitignore`，不能将本机工具状态提交到仓库。

## 2026-08-29：阶段 2 后端基础能力记录

- TDD 红阶段首次运行新增测试时，目标模块尚未创建导致测试收集失败；这是预期的失败先行信号，不应把它误判为实现回归。实现后必须重新运行完整测试集。
- zsh 中的 `path` 是特殊 PATH 数组变量。一次检查命令使用 `for path` 后导致后续 `sed` 不可用；以后使用 `file_name` 等普通变量名，避免覆盖 shell 保留变量。
- 路由响应曾错误地写成 `request_id(request_id(request))`，第一层调用返回字符串后被第二层当作 Request 使用；测试堆栈显示了完整调用链，修复后为每个路由直接调用一次请求编号解析函数。
- 微信适配器最初把原始 `unionid` 放入返回对象。即使不写入数据库，这仍然越过了适配器隐私边界；适配器现在只返回不可逆主体摘要，不能向后续服务传递原始 openid、unionid 或 session_key。
- CloudBase 适配器不能只用 mock 响应验证。官方文档核对后，查询使用 `documents:find`、更新使用 `documents:updateOne`、请求体使用 EJSON 字符串、认证头使用 CloudBase Open API 约定；这些路径和响应形状已写入适配器测试。条件更新无匹配时必须异步回查当前文档版本，再返回版本冲突。
- Ruff 和 mypy 的报错必须在阶段交付前清零；本阶段曾出现导入排序、行宽、SecretStr 类型、`app.state` 的 Any 类型和错误异常捕获等问题，均已修复并重新验证。

## 2026-09-02：阶段 4 学生端实现记录

- 本阶段首次从仓库根目录调用 `backend/.venv/bin/pytest` 和 `backend/.venv/bin/ruff` 时因工作目录已设置为 `backend/` 而报“文件不存在”；后端验证应在 `backend/` 工作目录使用 `.venv/bin/pytest`、`.venv/bin/ruff` 和 `.venv/bin/mypy`，避免重复拼接路径。
- 原生小程序组件事件需要通过组件 `triggerEvent` 传递；页面不能假设组件内部按钮的 `dataset` 会自动继承页面上下文，因此业务参数必须显式放在组件节点或事件 detail 中。
- 微信 WXML 不应依赖内联对象数组作为循环数据；底部导航改为组件 `data.items` 提供固定导航项，减少开发者工具解析差异。
- 安全确认的 `cannot_be_safe` 分支不能提供“返回继续观察”入口；支持资源页必须同时读取分支状态并隐藏继续按钮，避免绕过安全支持路径。

## 2026-09-02：阶段 5 后台 Web 工作台记录

- W-05 审计服务先以失败测试锁定筛选分页和真实环境重置拒绝；演示重置请求必须在环境与命名空间校验失败时直接返回，不开始逐集合写入。
- 并行实现阶段曾出现 `next_cursor` 可选类型、会话过期时间可选字符串以及路由引用尚未落盘的详情页错误；通过统一分页返回类型、为过期时间提供访问令牌回退并补齐 W-03 详情页后清零。以后共享工作区并行编辑后必须在格式化、类型检查和构建三个层面各自复核。
- 后台宽度阻断不能依赖 `body { min-width: 1280px; }`，否则窄屏浏览器会被强制横向放大而无法看到提示；应保持页面可缩放，由应用层在小于 1280px 时只渲染电脑浏览器提示。
- 任务动作接口只返回 `new_state`、`new_object_version` 和审计请求编号，不应把动作响应误解析为完整详情；提交后重新读取详情，冲突时转为只读状态。
- 新增后台服务测试使用 `@/` 路径时，Vitest 配置也必须声明与 Vite 相同的 alias；否则类型检查通过但测试收集会在模块解析阶段失败。
- 演示审计夹具不能在授权环境继续显示；W-05 按服务端返回的环境类型隔离演示数据，授权模式没有回退到演示事件。
