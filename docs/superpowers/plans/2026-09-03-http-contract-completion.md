# V2 HTTP Contract Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `BACKEND_STRUCTURE.md` 定义的 50 个本地 HTTP 端点全部注册并接入现有领域服务，使 APP_FLOW 的学生端和后台身份授权路径可以通过 FastAPI `TestClient` 复现。

**Architecture:** 保持 FastAPI 路由只负责认证、输入校验、服务调用和响应信封；新增学生核心、树洞和后台身份授权服务，扩展现有评估服务，并通过内存仓储提供类型化的版本控制与逻辑删除。所有写操作使用现有幂等服务和审计写入，真实 CloudBase 接入留在本地凭据到位后的部署阶段。

**Tech Stack:** Python 3.11.11、FastAPI 0.128.8、Pydantic 2.13.4、httpx 0.28.1、pytest 8.4.2、现有原生微信小程序和 Vue 后台。

**Spec:** `docs/superpowers/specs/2026-09-03-http-contract-completion-design.md`

## Global Constraints

- 所有 API 使用 `/api/v1`、`ApiEnvelope` 和稳定中文错误码。
- 路由不得直接访问数据库、评分、安全状态或密钥；服务层负责完整用例。
- 学生端和后台不得直连 CloudBase 管理接口或 DeepSeek；后端唯一云函数入口仍是 Python 3.11 `scf_bootstrap`。
- 真实身份只在身份域保存和读取；公开树洞只返回匿名展示投影。
- 未完成自测答案不入库；安全支持结果不保存完整答案、分数或 AI 快照。
- 所有变更先写失败测试，再实现最小代码；每组任务结束运行聚焦测试和全量后端测试。

## 文件地图

- Create: `backend/app/api/student_core.py`, `backend/app/api/treehole.py`, `backend/app/api/admin_identity.py`
- Create: `backend/app/services/account_service.py`, `backend/app/services/bootstrap_service.py`, `backend/app/services/treehole_service.py`, `backend/app/services/identity_access_service.py`
- Create: `backend/app/schemas/student_core.py`, `backend/app/schemas/treehole.py`, `backend/app/schemas/identity_access.py`
- Modify: `backend/app/main.py`, `backend/app/services/auth_service.py`, `backend/app/services/assessment_service.py`, `backend/app/repositories/domain_data_repository.py`, `backend/app/domain/models.py`
- Test: `backend/tests/test_student_core_api.py`, `backend/tests/test_treehole_api.py`, `backend/tests/test_identity_access_api.py`, `backend/tests/test_api_contract_registry.py`
- Docs: `docs/v2/COMPLETION_DEFINITION_ACCEPTANCE.md`, `progress.txt`, `lessons.md`

### Task 1: 端点注册门禁和学生账户创建

**Files:**

- Create: `backend/tests/test_api_contract_registry.py`
- Modify: `backend/app/main.py`, `backend/app/services/auth_service.py`, `backend/app/repositories/domain_data_repository.py`

**Interfaces:**

- `InMemoryDomainDataRepository.get_user_by_auth_subject_hash(subject_hash: str) -> UserAccountDocument | None`
- `InMemoryDomainDataRepository.create_user(user: UserAccountDocument) -> UserAccountDocument`
- `AuthService(..., domain_repository: InMemoryDomainDataRepository | None = None)`

- [ ] **Step 1: Write failing tests**：反射 `BACKEND_STRUCTURE.md` 端点并断言当前注册数为 50；用 FakeWechatClient 登录后断言用户账户可被后续服务读取。
- [ ] **Step 2: Run tests to verify failure**：`cd backend && .venv/bin/pytest tests/test_api_contract_registry.py -q`，预期端点对照失败且账户查找方法不存在。
- [ ] **Step 3: Implement minimal registry/account wiring**：新增仓储主体摘要查找/创建，`create_app` 将领域仓储传入 `AuthService`，登录时在发 token 前确保 active `UserAccountDocument` 存在；先注册后续路由占位模块以暴露准确缺口。
- [ ] **Step 4: Run tests**：同一聚焦测试通过，并确认旧认证测试仍通过。
- [ ] **Step 5: Commit**：`git add backend/app backend/tests/test_api_contract_registry.py && git commit -m "feat: wire student accounts and API contract gate"`

### Task 2: 学生核心接口（初始化、同意、身份、今日、心情、支持资源、账户）

**Files:**

- Create: `backend/app/api/student_core.py`, `backend/app/services/account_service.py`, `backend/app/services/bootstrap_service.py`, `backend/app/schemas/student_core.py`, `backend/tests/test_student_core_api.py`
- Modify: `backend/app/main.py`, `backend/app/services/consent_service.py`, `backend/app/services/identity_service.py`, `backend/app/services/today_service.py`, `backend/app/services/mood_service.py`, `backend/app/services/support_resource_service.py`, `backend/app/repositories/domain_data_repository.py`

**Interfaces:**

- `AccountService.stop/recover/status(access_token, object_version, request_id, idempotency_key) -> AccountState`
- `BootstrapService.get(access_token) -> BootstrapProjection`
- `student_core` routes consume existing consent/identity/today/mood/support services and return typed projections.

- [ ] **Step 1: Write failing tests**：覆盖 base/community 同意、身份核验创建/查询/匿名身份、`/me`、bootstrap、today、mood PUT/list/delete、support resources、account stop/recover/status；为每个写入测试缺失幂等键、身份/同意门槛和跨用户访问。
- [ ] **Step 2: Run focused tests**：`cd backend && .venv/bin/pytest tests/test_student_core_api.py -q`，预期模块/路由不存在或返回 404。
- [ ] **Step 3: Implement services, schemas and routes**：保持最小公开字段，重用现有领域服务；账户服务以事务更新恢复期状态并记录审计；bootstrap 在未同意时只返回非敏感配置；身份查询不返回姓名学号。
- [ ] **Step 4: Run focused and regression tests**：`cd backend && .venv/bin/pytest tests/test_student_core_api.py tests/test_auth_api.py tests/test_consent_identity_services.py tests/test_today_domain_services.py -q`。
- [ ] **Step 5: Commit**：`git add backend/app backend/tests/test_student_core_api.py && git commit -m "feat: expose student core API contract"`

### Task 3: 自测目录、会话放弃和结果接口

**Files:**

- Create: `backend/tests/test_assessment_http_contract.py`
- Modify: `backend/app/api/assessment.py`, `backend/app/services/assessment_service.py`, `backend/app/repositories/domain_data_repository.py`, `backend/app/schemas/assessment.py`

**Interfaces:**

- `AssessmentService.list_modules(access_token: str) -> list[AssessmentModuleProjection]`
- `AssessmentService.abandon_session(...) -> AssessmentSessionState`
- `AssessmentService.get_result/list_results/delete_result(...)`

- [ ] **Step 1: Write failing tests**：覆盖三个模块目录、开始/完成/放弃、普通/较高/睡眠/安全结果读取、列表、逐条删除和版本冲突；提交带 `score`、`safety_state` 或 `environment_id` 必须 422。
- [ ] **Step 2: Run focused tests**：`cd backend && .venv/bin/pytest tests/test_assessment_http_contract.py -q`，预期缺失路由/方法失败。
- [ ] **Step 3: Implement**：扩展 Pydantic 模型和服务投影；结果只允许本人访问，安全支持结果不返回分数/答案/AI；放弃事务清除未完成答案并幂等。
- [ ] **Step 4: Run tests**：`cd backend && .venv/bin/pytest tests/test_assessment_http_contract.py tests/test_assessment_api.py tests/test_assessment_service.py tests/test_safety_service.py -q`。
- [ ] **Step 5: Commit**：`git add backend/app/api/assessment.py backend/app/services/assessment_service.py backend/app/repositories/domain_data_repository.py backend/app/schemas/assessment.py backend/tests/test_assessment_http_contract.py && git commit -m "feat: expose assessment result API contract"`

### Task 4: 树洞帖子和回应接口

**Files:**

- Create: `backend/app/api/treehole.py`, `backend/app/services/treehole_service.py`, `backend/app/schemas/treehole.py`, `backend/tests/test_treehole_api.py`
- Modify: `backend/app/domain/models.py`, `backend/app/repositories/domain_data_repository.py`, `backend/app/main.py`

**Interfaces:**

- `TreeholeService.list_public/get_post/list_mine/create_post/withdraw_post/delete_post/create_response/delete_response`
- `TreeholeService` 所有写方法接受 `request_id`、`object_version`（适用时）和 `idempotency_key`。

- [ ] **Step 1: Write failing tests**：覆盖同意/身份/账户门槛、公开与保护投影、checking/pending/unpublished/safety_priority/deleted 状态、作者访问、回应、撤回、逐条删除、版本冲突和幂等冲突。
- [ ] **Step 2: Run focused tests**：`cd backend && .venv/bin/pytest tests/test_treehole_api.py -q`，预期目标服务和路由不存在。
- [ ] **Step 3: Implement**：增加树洞和回应仓储 CRUD；正文使用受保护存储边界，公开只返回脱敏摘要；固定规则决定初始 checking/人工任务，不接受客户端 visibility/review/safety 状态。
- [ ] **Step 4: Run tests**：`cd backend && .venv/bin/pytest tests/test_treehole_api.py tests/test_consent_identity_services.py -q`。
- [ ] **Step 5: Commit**：`git add backend/app backend/tests/test_treehole_api.py && git commit -m "feat: expose treehole API contract"`

### Task 5: 后台身份授权接口

**Files:**

- Create: `backend/app/api/admin_identity.py`, `backend/app/services/identity_access_service.py`, `backend/app/schemas/identity_access.py`, `backend/tests/test_identity_access_api.py`
- Modify: `backend/app/main.py`, `backend/app/domain/models.py`, `backend/app/repositories/domain_data_repository.py`, `backend/app/services/identity_service.py`

**Interfaces:**

- `IdentityAccessService.create_request/get_request/read_identity`
- 读取接口只接受服务端授权请求 ID，不接受客户端扩展字段。

- [ ] **Step 1: Write failing tests**：覆盖非后台拒绝、字段白名单、申请状态、批准/拒绝/过期、有效期和限定字段解密读取，以及每次读取审计。
- [ ] **Step 2: Run focused tests**：`cd backend && .venv/bin/pytest tests/test_identity_access_api.py -q`，预期模块/路由缺失。
- [ ] **Step 3: Implement**：增加请求仓储和服务；批准状态由后台任务决定，读取前复核 capability、范围、有效期和用户绑定；扩展身份密文解密边界，拒绝时不返回字段。
- [ ] **Step 4: Run tests**：`cd backend && .venv/bin/pytest tests/test_identity_access_api.py tests/test_admin_workbench_api.py -q`。
- [ ] **Step 5: Commit**：`git add backend/app backend/tests/test_identity_access_api.py && git commit -m "feat: add admin identity access API"`

### Task 6: 全量契约验收、文档和回归

**Files:**

- Modify: `backend/tests/test_api_contract_registry.py`, `docs/v2/COMPLETION_DEFINITION_ACCEPTANCE.md`, `progress.txt`, `lessons.md`

- [ ] **Step 1: Run full endpoint and privacy checks**：确认 `expected=50 actual=50 missing=0 extra=0`，运行三端门禁、配置示例、函数包、健康契约、隐私扫描和 `git diff --check`。
- [ ] **Step 2: Update acceptance docs**：第 12 节第 2、3 条改为本地通过；第 1、5 条仍明确标注真实凭据阻断；补充所有新增 HTTP 测试证据。
- [ ] **Step 3: Record lessons**：记录端点缺口根因、服务/路由边界、树洞投影和身份授权检查中的真实错误与修复。
- [ ] **Step 4: Commit and push**：`git add backend docs/v2/COMPLETION_DEFINITION_ACCEPTANCE.md progress.txt lessons.md && git commit -m "feat: complete local HTTP contract acceptance" && git push origin main`
