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
