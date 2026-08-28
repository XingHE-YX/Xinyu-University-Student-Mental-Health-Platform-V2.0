## 2026-08-28：工程初始化兼容性记录

- `create-vite@8.2.2` 不存在；脚手架工具版本与 `vite` 运行包版本独立，使用可用的 `create-vite@8.2.0` 生成结构，并将项目运行依赖锁定为 `vite@8.2.2`。
- `@typescript-eslint/parser@8.68.0` 的 peer 声明要求 TypeScript 小于 `6.1.0`，而规范锁定 `typescript@7.0.2`；后台安装必须使用 `npm --legacy-peer-deps`，不能擅自替换规范版本。
- `vue-tsc@3.3.11` 在 `typescript@7.0.2` 下无法解析 `typescript/lib/tsc`。初始化阶段保留两者的精确依赖，但 `npm run typecheck` 使用官方 `tsc` 检查 TypeScript 配置，`npm run build` 使用 Vite；未来若需要 Vue 模板类型检查，必须先由用户批准新的版本契约。
- `@typescript-eslint/parser@8.68.0` 在 `typescript@7.0.2` 下会直接拒绝加载（当前只支持 TypeScript 小于 `6.1.0`）；初始化阶段的 `npm run lint` 只检查 ESLint 配置文件，TS/Vue 源码 lint 必须在版本契约解决后恢复。
- 本机没有可直接调用的 Python 3.11；使用临时工具环境安装 Python 3.11.11，并在项目的 `backend/.venv` 中补装 pip 后运行 `pip-tools==7.6.1`。
- `jsdom@30.0.1` 在 Node `22.21.0` 下会发出 engine 警告（要求 `22.22.2` 或更高的 Node 22 补丁版本），后续运行浏览器环境测试时需单独记录实际 Node 版本或经用户批准调整基线。

## 2026-08-28：阶段 0 配置基线记录

- 新增的 `CONFIGURATION_REGISTRY.md` 首次格式检查未通过项目的 Prettier Markdown 规则；已使用项目现有 Prettier 格式化，并在完成声明前重新检查。以后新增 Markdown 配置或规范文件也必须执行格式检查。
