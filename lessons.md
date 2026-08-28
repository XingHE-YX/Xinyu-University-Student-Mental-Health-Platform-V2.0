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
