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
- 阶段 5 审查发现后台页面先于服务端工作台接口落地，导致任务与审计主要依赖本地演示夹具；已补齐 `/api/v1/admin/workbench`、任务详情与动作、审计分页和演示重置路由，并在 `create_app` 中注入可替换服务。
- 当前终端未把 `ruff` 和 `mypy` 放入全局 PATH；直接调用会报命令不存在，后端验证必须使用项目虚拟环境中的 `.venv/bin/ruff`、`.venv/bin/mypy` 和 `.venv/bin/pytest`。
- W-03 决定动作缺少提交前事实预览，且演示环境可选择真实联系结果；已增加上下文确认区，并在演示环境隐藏/拒绝 `contact_made`，服务端不接受客户端扩展身份字段。

## 2026-09-02：阶段 6 AI 受限辅助记录

- 阶段 6 首次执行新增测试时，目标适配器、策略和服务模块尚未创建，测试收集阶段出现 `ModuleNotFoundError`；这是 TDD 红阶段的预期失败，实现后必须重新运行完整测试集。
- 新增测试最初误用了不存在的 `app.audit.repository` 导入路径；项目审计仓储实际位于 `app.repositories.audit_repository`，以后新增后端测试应先沿用现有目录边界核对导入路径。
- 冻结提示词包含长中文行，Ruff 的 E501 会将提示词文本误判为代码行；已仅对 `app/config/ai_prompt.py` 设置文件级 E501 忽略，策略代码仍保持默认 100 列限制，新增提示词文件必须单独执行格式和静态检查。
- AI 输出即使结构合法、但 `status="needs_fallback"` 时也必须进入服务端固定回退，不能把模型主动请求回退误当作已采用结果；回退审计只记录任务类型、模型/提示词版本、结果类别和错误类别。
- 自测辅助摘要长度要求为 40 至 90 个汉字；服务端输出校验必须执行契约中的长度、枚举、证据片段和违禁内容检查，不能只校验 JSON 可解析。

## 2026-09-02：阶段 7 部署和环境初始化记录

- 隔离 worktree 不会继承被 Git 忽略的 `backend/.venv`；首次从错误工作目录调用 `.venv/bin/pytest` 报文件不存在。以后每个 worktree 都要显式用 Python 3.11 创建虚拟环境，并在 `backend/` 目录执行 `.venv/bin/pytest`、`.venv/bin/ruff` 和 `.venv/bin/mypy`。
- 在 macOS 上直接按锁文件安装依赖会把 Darwin 原生 wheel 放进 CloudBase 函数包，不能上传到 Linux 运行时。函数打包器现在强制 `--platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all:`，并验证重复构建产物确定性。
- 依赖包中的 `certifi/cacert.pem` 是公开 CA bundle，不应被“禁止 `.pem` 文件”的秘密扫描误报；扫描器只阻止 `.env`、私钥容器后缀和 credentials/secrets 文件名。
- CloudBase、微信开发者工具和静态托管的真实凭据在当前工作区仍未提供；阶段 7 只能提交模板、校验器和可复现本地构建，不能伪造 EnvID、AppID、域名、密钥或把 Python 包伪装为其他运行时。
- Vite `dist` 预览需要验证根路由和深层路由刷新都回退到 `index.html`；仅检查构建成功不足以证明 SPA 静态托管配置正确。
## 2026-08-30：阶段 3.1 集合、索引和种子数据记录

- 当前终端没有 `python` 命令，直接执行阶段脚本曾出现 `zsh: command not found: python`；随后直接把 shell 脚本交给 Python 又出现 `SyntaxError: invalid syntax`（脚本首行是 `set -euo pipefail`）。Python 校验必须使用项目 Python 3.11 解释器，Shell 工具必须使用 `bash` 调用。
- 阶段审查工具脚本缺少可执行权限，直接运行曾出现 `Permission denied`；已改用 `bash` 和明确的计划文件、输出文件路径执行，避免把工具权限问题误判为代码失败。
- 规范的 `auth_sessions` 字段表使用 `access_expires_at`，索引表最初误写成 `expires_at`。若把冲突原样写入部署索引会生成不可执行索引；本阶段统一为 `access_expires_at`，并在注册表测试中验证每个索引字段都存在于集合字段中，同时修正文档索引表。
- IMPLEMENTATION_PLAN.md 的阶段 3.1 文字称 23 个集合，但权威集合清单包含 `ai_assist_snapshots`，实际为 24 个。本阶段以 BACKEND_STRUCTURE.md 和后续结果边界为准，保留 24 个集合并在 progress.txt 记录。
- 领域模型不能只声明枚举：同意/审计记录的 `version` 固定为 1，未完成自测会话不能保存答案，安全支持结果不能保存完整答案、分数或 AI 快照，`cannot_be_safe` 不生成结果；这些状态/隐私边界已通过 Pydantic 校验和行为测试锁定。
- 短句种子不能只校验“40+3”的数量；本阶段增加了 Q-0001、Q-0040、Q-C001..Q-C003 内容级断言，并让全部 43 条种子逐条通过 `QuoteEntryDocument` 校验。现代作品候选继续保持 `copyright_pending` 且禁用。
- 本地静态检查使用的 `backend/.packages/` 是未跟踪的依赖缓存，不能提交到仓库；首次审查环境缺少已编译的 `pydantic_core`，第二轮代理又因工作区额度耗尽中止，均属于验证环境问题，最终使用项目 Python 3.11 环境重新完成测试、Ruff、mypy 和编译检查。
- 提交后的 Markdown 检查若把 `progress.txt` 一并交给 Prettier，会报 `No parser could be inferred for file .../progress.txt`；单独检查 `lessons.md` 通过。`BACKEND_STRUCTURE.md` 和既有的 `AGENT.md` 本身存在历史格式差异，未对整份规范文档做无关的全量重排，本阶段只校验了实际变更并修正索引字段。

## 2026-08-31：阶段 3.2 同意和身份核验记录

- TDD 红阶段的聚焦测试先因尚未创建 `app.repositories.domain_data_repository` 出现 `ModuleNotFoundError`；这是预期的实现先行信号。补齐本地领域仓储后，3.2 相关聚焦测试达到 53 项通过，不能把第一次收集失败误判为最终回归。
- 身份请求的幂等摘要不能使用固定占位符。姓名和学号必须使用稳定、可区分且不含原文的 keyed digest；这样相同幂等键可以安全重放，也能识别不同身份输入的 `IDEMPOTENCY_CONFLICT`，同时不把原文写入幂等记录或日志。
- 同意状态、身份记录、匿名身份和账户指针属于一个领域写入边界。先写部分文档再更新账户会产生半成功；本地实现用带锁事务、版本复核和异常回滚覆盖用户、身份、匿名身份、同意事件及 ID 计数器，接入 CloudBase 时必须保留同样的原子或补偿语义。
- 失败幂等重放必须保留完整的安全错误契约，包括 `code`、`message`、`status_code`、`retryable` 和 `current_version`。只保存错误码会让第一次版本冲突和重放返回不同的服务器事实；终态幂等记录也不能被后续完成调用覆盖。
- 未知运行时异常也必须完成幂等失败记录，避免记录永久停在 `processing`。但成功幂等完成之后的审计写入属于独立的 best-effort 边界；审计异常不能把已成功的业务状态反写成失败，日志只能记录不含姓名、学号和其他敏感原文的固定信息。
- 学校核验返回 malformed JSON、非对象或传输异常时统一归一为 `unavailable`；失败和不可用记录不保存姓名、学号密文，也不生成新的匿名身份。已 `verified` 记录的重复核验应保持原事实，不因临时依赖故障降级。
- 当前默认身份密文使用 `enc:v1` 的本地 HMAC 派生保护边界，已避免明文和固定密文重复，但生产接入前仍需替换为标准 AEAD、受管理密钥和密钥轮换方案；本阶段没有引入不在锁定依赖中的第三方加密包。

## 2026-08-31：阶段 3.3 题卷和固定评分记录

- 3.3 红阶段首次运行时发现工作树的 Python 3.11 虚拟环境失效，`pytest` 与解释器都不能直接执行；重建并安装锁定依赖后才得到真实的“实现模块尚未创建”失败。以后先确认当前工作树解释器和测试入口可用，再判断测试红灯原因。
- 运行时题卷不能只依赖代码内置目录。模块是否启用、当前题卷版本和对应题目必须由仓储发布态决定；开始会话时冻结该版本，完成时使用同一冻结题卷校验和评分，否则会绕过禁用开关或把 v2 会话按旧题卷计算。
- 固定结果文案属于产品契约，不是可随意压缩的提示语。PHQ-9、GAD-7 分段总结、筛查边界和睡眠结果开场均需逐字对齐冻结规范，并用文本断言锁定，避免评分正确但用户看到错误语义。
- PHQ-9 第 9 题非零必须在所有后续结果路径前拦截：首次提交进入 `safety_confirmation_required`，已有 `cannot_be_safe` 状态进入 `safety_support_blocked`，两者都不能保存未完成答案或生成普通结果。安全确认、资源确认和安全任务由 3.4 负责，3.3 只守住结果生成边界。
- 题卷完成请求只能接受 `question_key` 和 `option_key`；服务端重新计算 `score_snapshot`、分数、分段和结果状态。睡眠第 8 题的多选/跳过/“不想回答”互斥规则必须在服务端校验，不能由前端选择状态代替。
- 评审发现并修复了“不能安全”分支构造阻断响应后继续落库的安全漏洞；以后对每个安全分支都要测试响应、会话状态、答案持久化和结果集合四个维度，而不能只断言返回状态。
- 当前 3.3 没有接入 HTTP，也没有实现 3.4 安全任务或 3.5 今日/树洞服务；后续路由接入时必须保持题卷公开投影不包含 `score_rule`，并继续使用服务端结果作为唯一事实来源。

## 2026-09-01：阶段 3.4 简报工具兼容性记录

- `task-brief` 脚本默认直接执行 `sdd-workspace`，而当前技能缓存中的该脚本没有可执行权限，首次运行报 `Permission denied`；计划任务标题也使用阶段编号而不是 `Task N`，因此无法自动抽取 3.4。已保留错误事实，改为用 `bash` 调用脚本并按计划原文手工生成唯一的 3.4 简报，后续审查仍以该简报为单一需求入口。

## 2026-09-01：阶段 3.4 安全支持和任务服务记录

- 阶段 3.4 的 TDD 红阶段按预期先暴露 3 个行为缺口：实际资源类别被占位值 `safety` 覆盖、`uncertain` 可被后续确认改写为 `can_be_safe`、`work_tasks.source_type` 与其来源 ID 不匹配。修复后聚焦测试 23 项和后端全量测试 134 项通过；以后安全分支必须同时验证投影、会话状态、资源确认和结果/任务集合。
- 首轮复审发现 `uncertain` → `can_be_safe` 会绕过资源确认并产生普通结果；已在服务端状态机拒绝该改写，并加入不同幂等键的回归测试。客户端返回或导航不能成为安全状态的写入事实。
- 首轮复审还发现受限结果把 `resource_categories_shown` 写成固定占位类别，以及 `work_tasks` 用 `assessment_result` 类型指向安全任务文档；已改为读取当前环境真实启用类别，并统一使用 `source_type=support_task` 与安全任务 ID。
- 3.4 首次尝试中实现代理在已完成修复、测试和暂存后因工作区额度耗尽中止，未能自行提交；保留其暂存改动并由主流程复核、验证和提交。遇到代理额度错误时先检查是否留下完整、可审查的变更，不能直接丢弃或假设未完成。
- 首次调用复审脚本时误用了 `executing-plans/scripts/review-package` 路径，得到 `No such file or directory`；实际脚本位于 `subagent-driven-development/scripts/review-package`。工具路径错误只记录为流程问题，不改变产品实现判断。
- 最终文档校验直接调用 `prettier` 时因当前工作树未安装 Node 依赖而报 `command not found: prettier`；随后使用项目锁定的 Prettier `3.9.6` 临时执行校验并通过。以后先确认工作树的依赖是否存在，再选择项目本地或锁定版本的临时执行入口。
- 支持资源读取 API 仍属于 3.5；3.4 只保留安全确认所需的服务端资源版本/类别读取，避免提前扩展学生端 API 边界。`cannot_be_safe` 继续不生成 `assessment_results`，任务使用内部受限引用保持可追踪性，后续后台详情落地时再评估专用安全事实集合。

## 2026-09-01：阶段 3.5 简报工具兼容性记录

- `task-brief` 在阶段 3.5 仍因内部调用的 `sdd-workspace` 没有可执行权限而报 `Permission denied`；已按阶段计划原文手工建立唯一简报，并将 3.5 的四个服务、精确数据边界和测试要求写入其中。以后运行技能脚本时直接用 `bash` 调用底层脚本或保留手工简报，不把权限错误误判成实现失败。

## 2026-09-01：阶段 3.5 今日、心情、短句和支持资源记录

- TDD 红阶段按预期先因四个目标服务尚未创建出现 `ModuleNotFoundError`；实现后聚焦测试达到 6 项通过，修复回归后达到 7 项通过，不能把先行失败误判为最终回归。
- 阶段 3.5 首次调用 `review-package` 时把计划参数写成了不存在的 `IMPLEMENTATION_PLAN`，报 `no such plan file`；实际计划文件是 `IMPLEMENTATION_PLAN.md`，修正参数后成功生成复审包。工具参数错误只记录为流程问题，不改变代码审查结论。
- 首轮复审发现已删除心情记录仍可被重复删除并增加版本；修复时必须把墓碑状态作为事务内的终态，并用真实仓储和审计断言验证无二次写入。修复后独立 scoped re-review 已通过。
- 历史心情筛选的 `from_date`/`to_date` 格式校验被复审列为 deferred Minor；当前阶段保留 owner-scoped、未删除过滤语义，后续 API hardening 时再补格式化错误契约，避免在本阶段扩大接口范围。
- 最终验证首次执行 Ruff 格式检查时发现 `today_service.py` 和 3.5 聚焦测试各有一处未按当前 Ruff 版本折叠/展开的表达式；已用项目虚拟环境的 Ruff 格式化并重新验证，功能逻辑未改变。以后提交前必须同时运行 `ruff check` 与 `ruff format --check`，不能只看规则检查结果。

## 2026-09-01：阶段 3.5 修复后复审和交付记录

- 第一轮全分支复审发现并修复了跨阶段契约问题：安全支持任务与 work task 的统一 ID、`cannot_be_safe` 的真实会话引用、PHQ-9 第 9 题归零时清理临时安全状态、心情删除幂等、短句随机与即时去重、支持资源版本/过期过滤、assessment 审计枚举和短句来源字段。生产 CloudBase 领域仓储接入经控制器裁定属于后续 API/部署集成范围，不能为完成 3.5 擅自扩大到生产持久化 wiring。
- 修复后复审第一轮又发现两个 Important：学生端短句投影错误暴露 `quote_id`，以及候选池未强制 `review_status=已启用`。本地复现确认 `enabled=True` 且待核验的条目确实会泄漏到候选池；已在 `cd46927d` 中移除投影字段、保留内部上一条排除能力，并补上仓储过滤与回归测试。第二轮 scoped re-review 已批准。
- 本轮修复后验证结果为 today/domain 聚焦测试 21 项、后端全量 148 项通过；Ruff check/format、mypy、compileall 和 `git diff --check` 全部通过。两次独立复审均无未解决的 Critical/Important/Minor；历史日期筛选格式校验仍为 deferred Minor。
- 文档检查曾直接把 `progress.txt` 交给 Prettier，报 `No parser could be inferred for file .../progress.txt`；对既有规范 Markdown 使用临时 Prettier 还提示历史排版差异。由于仓库没有 Markdown 格式配置，且整篇重排会引入无关变更，本阶段以 `git diff --check`、Ruff/mypy/测试为门禁，并保留该工具报错记录。
- 复现复审问题时曾从仓库根目录调用后端 Python，报 `ModuleNotFoundError: No module named 'app'`，随后在后端工作目录误用了 `backend/.venv/bin/python` 报路径不存在；改用后端目录下的 `.venv/bin/python` 后完成有效复现。以后执行后端临时脚本必须同时确认工作目录和解释器相对路径。
- 第一次提交交付记录时对已跟踪但位于被忽略目录的任务报告执行普通 `git add`，Git 提示该路径被 ignore；状态检查确认文件仍已被跟踪并已暂存，随后提交成功。以后遇到此提示先用 `git ls-files`/状态确认跟踪关系，不要使用宽泛强制添加覆盖无关忽略文件。

## 2026-09-02：阶段 3.1–3.5 最终复审记录

- 最终全分支只读复审从 3.1–3.5 基线到 `aada9ff` 通过，确认 117 项针对性检查、Ruff、格式、compileall、demo seed 和差异检查均无阻塞问题；没有新增 Critical、Important 或未解决 Minor。3.5 的学生 HTTP/API 与树洞行为继续留给阶段 4。

## 2026-09-02：阶段 8 完成前验收记录

- 阶段 8 首次在仓库根目录直接调用 `ruff` 报 `command not found`；本项目应在 `backend/` 工作目录使用锁定虚拟环境中的 `.venv/bin/ruff`、`.venv/bin/mypy` 和 `.venv/bin/pytest`。后台当前终端为 Node `v26.8.1` / npm `11.19.0`，而项目锁定 Node `22.21.0` / npm `10.9.4`；门禁虽已通过，清洁发布仍需切换锁定工具链。
- 函数包第一次验收时从 `backend/` 目录对相对输出路径执行哈希，误把产物写到仓库根目录 `dist/` 后又在 `backend/dist/` 查找，得到“文件不存在”；构建脚本的输出路径相对于仓库根目录解析，验收时必须先确认实际产物位置。
- CloudBase `manifest.template.json` 仍含占位 EnvID、命名空间和域名，直接运行校验器会按设计返回 `is not configured` 和 HTTPS 错误；只有 `manifest.example.json`（合成的 example.invalid 来源）可作为结构示例通过，真实值必须在被忽略的本地渲染文件中校验。
- 微信开发者工具游客 AppID 的 CLI 预览先报“二维码输出路径无效或不存在”，终端预览又报 `INVALID_LOGIN, access_token expired`；模拟器本地编译和页面渲染仍成功，这些是游客凭据/工具环境阻断，不是小程序 TypeScript 编译错误，也不能当作真实发布验收。
- 阶段 8 对照 APP_FLOW 检查时确认当前学生端在未配置 API 地址时使用演示响应夹具；真实同意、身份核验、心情、自测、树洞和账户接口联调需要 CloudBase Python API 和真实 AppID，不能把演示夹具结果写成授权环境通过。
- 阶段 8 文档检查对整份 `lessons.md` 报 Prettier 风格差异；该文件包含各阶段已审阅的历史排版，未对全文做无关重排，仅对新增 `docs/v2/PHASE_8_ACCEPTANCE.md` 执行格式化并以 `git diff --check` 作为历史文档门禁。

## 2026-09-02：第 12 节完成定义验收记录

- 第 12 节接口对照首次按 `BACKEND_STRUCTURE.md` 和 FastAPI 路由反射执行，确认规范当前定义 50 个端点而运行时仅注册 18 个，缺少 32 个端点。领域服务已存在不能视为 HTTP 契约已实现；后续接入路由时必须为每个端点补齐认证、权限、错误信封和最小投影测试。
- 本轮首次重跑函数包哈希时从 `backend/` 使用了相对于仓库根目录解析的输出路径，哈希命令报 `No such file or directory`；改用仓库根目录和显式 `backend/dist/...` 路径后，两次 SHA-256 一致。构建脚本的输出路径以仓库根目录为基准，验收命令必须先确认产物实际位置。
- 本轮首次运行接口对照脚本时使用系统 Python，导入 FastAPI 报 `ModuleNotFoundError: No module named 'fastapi'`；改用 `backend/.venv/bin/python` 后得到有效的 50/18/32 对照结果。所有后端脚本必须使用项目锁定的 Python 3.11 虚拟环境。
- 函数包秘密扫描最初把依赖中的 `mypy/typeshed/stdlib/secrets.pyi` 误报为秘密文件；项目打包器只阻止 `.env`、`credentials`、`secrets` 精确文件名及 `.key`/`.p12` 后缀，验收扫描必须采用同一规则，不能把合法依赖类型存根当作密钥。
- 设计验收发现学生端仍有多处 WXML `style=`，违反 `AGENT.md` 的硬约束；已统一改为 WXSS 语义类，并把动态百分比进度改成分段进度组件。以后设计验收必须直接扫描 `*.wxml` 和 `*.vue` 的内联样式属性。

## 2026-09-03：第 12 节本地阻断修复和最终验收记录

- 评估 HTTP 适配器初版把模块级 `_decode_session_state_response` 当成实例方法调用，且 `AssessmentResultDocument` 的内部 `cannot_be_safe` 枚举直接传入公开投影；mypy 分别报属性不存在/返回 `Any` 和 Literal 不兼容。修复为模块函数调用，并在投影边界显式拒绝该不变量，避免内部安全阻断状态泄漏。
- 树洞确认排序初版使用了反向布尔条件，导致 `published` 排在 `protected` 前；新增排序回归测试并改为 `visibility_state == "protected"`，确认展示优先级与契约一致。树洞状态变量同时补上 Literal 标注，避免字符串推断绕过模型枚举。
- 为保持既有身份核验测试替身兼容，身份加密 Protocol 不能把只读 `decrypt` 设为所有实现的必需方法；已将解密保留在 `HmacIdentityCipher` 的身份授权边界，并由授权服务在运行时检查可选能力。这样既不削弱生产解密边界，也不迫使仅负责加密的测试替身伪造解密实现。
- 后台身份授权服务和树洞服务的主体辅助函数缺少返回类型，严格 mypy 将其作为阻断；统一标注 `AuthenticatedSubject`，并新增路由契约测试持续保护 50 个接口。
- 第 12 节修复后验证顺序必须覆盖静态类型、聚焦 HTTP、安全分支、全量后端、三端构建、配置示例、函数包和健康检查；本轮最终结果为后端 180 项、聚焦回归 40 项通过，端点反射 `50/50`。文档中的发布结论应区分“本地通过”和“真实凭据待配置”，不能把 `example.invalid` 或 `status=degraded` 写成线上完成。
- 删除类接口的 `object_version` 位置必须与 HTTP 合同和客户端请求方式一致；本地客户端通过 DELETE 请求体发送版本后，统一改为 Pydantic body 校验，并补充缺失资源的错误信封回归，避免查询参数与请求体契约漂移。

## 2026-09-03：第 12 节最终验收命令复核记录

- `validate_manifest.py` 只接受 manifest 文件路径，误传 `--help` 会把参数当作文件并报 `FileNotFoundError`；先查看脚本源码或使用实际示例文件，不能假设所有脚本都提供 argparse 帮助。
- 在 `backend/` 工作目录启动 Uvicorn 时误用了仓库根目录相对路径 `backend/.venv/bin/uvicorn`，得到 `no such file or directory`；工作目录内应使用 `.venv/bin/uvicorn`。
- 通过 shell 内嵌 Python 做路由统计时曾因引号未闭合、正则反斜杠过度转义和根目录缺少 `app` 导致无效结果或 `ModuleNotFoundError`；最终使用项目解释器、`PYTHONPATH=backend` 和可读的 heredoc 脚本得到 `expected=50 actual=50`。
- 函数包秘密扫描若按任意路径段匹配 `secrets`，会误报依赖中的 `mypy/typeshed/stdlib/secrets.pyi`；验收必须复用打包器的精确规则（basename 为 `credentials`/`secrets`、`.env*` 或 `.key`/`.p12` 后缀），公开类型存根不属于秘密文件。

## 2026-09-13：微信真机调试 Sitemap 校验记录

- `sitemap.json` 只有 `desc` 时，模拟器本地编译仍可运行，但真机调试上传会报 `-80055 Invalid SiteMap`；文件必须包含非空的顶层 `rules` 数组。补齐标准 `allow` 规则后，真机调试重新打包并成功生成二维码。


## 2026-09-16：软著说明书本地联调与截图

- 本次以 XinYu-V2 实际运行界面生成45页使用说明书，包含45张原始界面截图、2张架构/流程图与50个实际注册接口。材料位于 `docs/copyright/2026-09-16/02-软件使用说明书/`；源码材料已同步更新为60页、每页至少50行。
- 学生端联调必须使用服务端题卷返回的 question_key、option_key 和动态 object_version；完成接口只返回结果引用时，要再读取结果详情，不能把完成响应直接当作完整结果。
- 账户摘要从 `/app/bootstrap` 读取，正确解析嵌套同意状态；账户停止与恢复先读取最新版本。已核验账户再次登录直接进入今日，避免重复核验引发版本冲突。
- 本地预览仅在微信开发者工具、演示模式且无显式外部配置时使用127.0.0.1；设备端不启用回环地址，也不覆盖显式授权环境配置。`deploy/local/` 提供可复现入口，使用合成身份和内存数据，不能描述为正式云端验收。
- 本机基础库3.17.2下官方自动化可读取工具信息，但Page.getData等命令超时；切换已验证的3.16.1后完成输入与流程取证。取证结束已关闭官方自动化会话并恢复原私有基础库设置。
- 浏览器全页截图在当前视口覆盖下曾出现内容缩到左上角的问题；审计图已改用正常视口截图重新采集。Word完成后必须转PDF核对图注、实际图片、中文字体和空白页，不能只检查docx包内图片数量。

## 2026-09-17：联网清单第 1 项配置判定修复

- 配置测试只显式传入白名单会漏掉默认启动无法识别环境的问题。默认启动现读取 `CLOUDBASE_ENV_ID_DEMO` / `CLOUDBASE_ENV_ID_AUTHORIZED`，并用真实 `create_app()` 入口测试；不能把当前目标 EnvID 按 `DEMO_MODE` 自动加入白名单。
- DeepSeek 属于可选辅助，缺少 Key 不应阻断登录和固定规则；回归必须同时检查核心环境就绪和 AI 固定回退。其他核心配置仍必需，模板占位符不视为有效配置。
- manifest 的微信密钥引用原为 `WECHAT_APP_SECRET_*`，与后端及 YAML 的 `WECHAT_APPSECRET_*` 不一致，且漏列会话密钥；已统一命名并补齐引用。配置就绪和健康接口 `status=ok` 不等于云数据库持久化或真实依赖联调已完成。

## 2026-09-21：联网清单第 3 项 CloudBase 持久化

- 早期 CloudBase 适配器按旧资料实现 `/api/v2/envs/.../documents:find` 和 `X-CloudBase-Authorization`，模拟测试会通过但真实平台已使用环境网关 `/v1/database/...` 与 `Authorization: Bearer`。外部适配器必须用实际环境做不泄密的只读连通检查，并以当前官方 OpenAPI 锁定路径、EJSON 和事务合同。
- 文档型数据库当前 HTTP API 支持 Python 后端使用的事务；所有业务仓储共享同一个 `CloudBaseStore`，事务 ID 用请求上下文隔离。真实验证必须覆盖提交、回滚、陈旧版本和重启恢复，不能只检查集合存在。

## 2026-09-21：联网清单第 4 项 Python 云函数部署

- CloudBase 控制台的“API Key 设置”固定以 `CLOUDBASE_APIKEY` 注入托管 Key，与项目模板原先使用的 `CLOUDBASE_API_KEY` 不同。部署前必须核对平台实际变量名；后端兼容两者，并优先保留模板变量以支持其他部署方式。
- HTTP 云函数创建成功不会自动生成路由。体验版已有默认 `app.tcloudbase.com` 域名，可在 HTTP 网关为 `/` 添加“云函数 HTTP”路由；函数详情中的“添加域名”是付费自定义域名能力，不是获取默认访问地址的必要步骤。
- 线上健康接口返回 HTTP 200 只证明网关和进程可用。当前 `degraded` 是缺少微信、后台、学校和支持资源配置的正确结果，不能为了显示 `ok` 填入占位凭据。
- 幂等持久化还需要保存 `record_id` 和 `response_status`，审计持久化需要保存经过白名单过滤的 `details`；仅按旧字段表落库会让失败重放或最小事实丢失。字段合同、注册表和索引计划必须一起更新。
- 初始化脚本直接以文件路径运行会因工作目录和导入路径报 `ModuleNotFoundError: app`；本项目在 `backend/` 目录使用 `.venv/bin/python -m scripts.initialize_cloudbase ...`。首次成功创建 24 个集合、31 个索引和 57 条合成文档，第二次重跑保持数量不变。

## 2026-09-21：联网清单第 5 项测试号微信登录

- 微信“小程序测试号”后台直接显示 AppID/AppSecret，没有正式小程序后台的“开发管理”菜单；不能按正式账号导航误导操作者。测试号只用于联调，不能作为微信审核发布凭据。
- 密钥出现在截图后不能再视为正式长期凭据。CloudBase 普通函数环境变量也会向有控制台权限的操作者显示原值；演示可继续使用一次性测试密钥，正式发布必须改用正式账号并轮换。
- 小程序真机不能依赖开发者工具专用的 `127.0.0.1` 回退，也不能假定普通项目自动拥有外部配置。当前使用被 Git 忽略的 `miniprogram/ext.json` 提供 AppID、EnvID 和 HTTPS API 地址，文件中禁止出现任意 AppSecret/API Key。
- 全局 `configuration_status` 适合健康状态，不应让尚未配置的后台、学校或支持资源阻断微信登录本身。学生登录按功能检查微信凭据、环境登记、稳定会话密钥和持久化；后续功能仍在各自边界返回明确未配置状态。
- 普通小程序测试号真机没有读取 `ext.json`，即使开发者工具预览编译成功，运行时仍可能得到空外部配置。普通真机配置改为根据 `wx.getAccountInfoSync()` 返回的 AppID 匹配集中式非秘密部署表；未知 AppID 不能回退到 demo，`ext.json` 只保留为代开发/工具覆盖手段。
- 微信登录成功不等于私密功能可用。CloudBase 新增账户、会话和基础同意后，身份仍未绑定；跳过身份页时自测、心情和发布由服务端继续拒绝。演示环境使用固定合成身份适配器，且必须由服务端确认登记过的 demo EnvID；正式和未知环境禁止复用该适配器。
- 身份页允许“稍后再做”时，主界面必须提供返回身份核验和退出登录的恢复入口。只在自测/发布动作中被动重定向会让用户误以为账号被困住；本地退出即使服务端暂时不可达也要清除会话，服务端令牌按既有过期边界失效。
- 配置 DeepSeek Key 不代表业务已接入。必须从实际路由追踪到服务调用、持久快照和客户端投影；本轮发现 `AiAssistService` 只挂在 `app.state`、没有任何业务调用，补齐自测完成后的受限调用后才可称为可展示功能。
- DeepSeek 验收不能只看 Key 非空。使用合成无个人信息请求验证 HTTP 状态、JSON 格式、任务类型和输出状态；真实请求通过后仍必须保留超时、结构校验、策略复核和固定回退。
- CloudBase 静态托管默认域名首次访问会显示测试域名风险提示，且只适合开发演示；404 到 `/index.html` 的重写是 SPA 深层刷新必需配置。静态托管域名加入 HTTP 网关 WEB 安全域名后，必须用 OPTIONS 预检验证精确来源、方法和认证/幂等请求头。
- 树洞 AI 接入不能把临时原文或模型建议当成最终公开决定。调用前只使用临时脱敏文本，持久化快照只保留输入摘要和通过策略校验的投影；帖子/回应状态继续由规则和人工流程决定，安全信号内容不进入普通 AI 审核。
- 只创建领域详情任务集合不足以让后台看到真实任务；学生端业务动作还必须同步写统一 `work_tasks` 索引，并保持 task ID、source_type/source_id、能力和对象版本一致。否则后台演示只能看到种子任务，无法闭环真实小程序操作。

## 2026-09-22：答辩最终部署与后台联调

- 管理后台的 `VITE_API_BASE_URL` 已包含 `/api/v1` 时，服务路径必须从 `/admin/...` 开始；再次写 `/api/v1/admin/...` 会形成重复路径并得到不符合统一信封的 404。生产构建必须显式注入 API 地址，并在构建产物中同时检查正确来源和禁止 `/api/v1/api/v1`。
- 静态托管更新不能只看本地构建成功；必须核对 CDN 返回的新 JS/CSS 指纹及其内嵌 API 来源。缺失构建变量时，后台会把请求错误发送到静态网站自身。
- 长任务 ID、对象 ID 和主体哈希必须在 Grid/Flex 子项上同时设置 `min-width: 0` 与 `overflow-wrap: anywhere`。只改变外层列数仍会让默认最小内容宽度撑破边界；审计列表和详情在窄桌面下应上下排列。
- 后台内容审核任务不能只改变 `work_tasks` 状态；人工决定必须在同一事务边界同步更新树洞帖子或回应。DeepSeek 只提供经校验的建议和脱敏说明，不能自动公开内容。
