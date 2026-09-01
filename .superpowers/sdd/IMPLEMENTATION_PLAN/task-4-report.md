# Task 4 report — 阶段 3.4 安全分支

## 实现内容

- 新增固定安全状态机 `backend/app/domain/safety_rules.py`，包含三种确认状态、固定问题/选项文案、三路 `next_step` 和安全状态最小可见投影。
- 新增 `SafetyService`，接入 PHQ-9 第 9 题非零安全确认、资源展示确认、对象版本检查、幂等、防客户端状态字段篡改、审计最小事实和演示/授权环境任务创建边界。
- 扩展 `AssessmentService` 的完成流程：
  - `can_be_safe` 允许继续完成并生成 ordinary/higher_score，且不创建安全任务；
  - `uncertain` 必须先确认同一会话、同一 `resource_version` 的安全资源展示；最终完成后只保存 `safety_support` 受限结果，不保存完整答案、分数、参考分层或 AI 快照，并在 demo/authorized 环境创建最小安全任务；
  - `cannot_be_safe` 由安全确认接口立即标记会话 `abandoned`，不生成 assessment result，进入 support_only。
- 扩展内存领域仓储，支持 `support_resources` 窄读取、`safety_support_tasks` 和 `work_tasks` 原子创建、事务回滚和确定性 ID。
- 新增 HTTP 路由：
  - `POST /api/v1/assessment-sessions/{session_id}/safety-confirmation`
  - `POST /api/v1/assessment-sessions/{session_id}/support-resource-ack`
  路由只处理认证头、幂等键、Pydantic 输入边界和 envelope 序列化。
- 新增行为测试覆盖三种安全确认分支、Q9 为零拒绝、部分答案不落库、uncertain 资源确认前阻断、资源版本冲突、can_be_safe 不建任务、uncertain/cannot 在允许环境建最小任务、unconfigured 不建任务、重复提交幂等、对象版本冲突、任务/结果最小投影和客户端状态字段篡改拒绝。

## 修改文件

- `backend/app/domain/safety_rules.py`
- `backend/app/services/safety_service.py`
- `backend/app/api/assessment.py`
- `backend/app/schemas/assessment.py`
- `backend/app/services/assessment_service.py`
- `backend/app/domain/models.py`
- `backend/app/repositories/domain_data_repository.py`
- `backend/app/main.py`
- `backend/tests/test_safety_service.py`
- `backend/tests/test_assessment_api.py`

未纳入本次提交：`lessons.md` 在接手时已有未提交改动，本任务未修改或提交该文件。

## TDD RED

命令：

```bash
backend/.venv/bin/python -m pytest backend/tests/test_safety_service.py backend/tests/test_assessment_api.py
```

实际输出：

```text
============================= test session starts ==============================
platform darwin -- Python 3.11.11, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/xingheluqi/XinYu-V2/.worktrees/phase-3-backend-domain-data/backend
configfile: pyproject.toml
plugins: asyncio-1.2.0, anyio-4.14.2
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 0 items / 2 errors

==================================== ERRORS ====================================
________________ ERROR collecting tests/test_safety_service.py _________________
ImportError while importing test module '/Users/xingheluqi/XinYu-V2/.worktrees/phase-3-backend-domain-data/backend/tests/test_safety_service.py'.
Traceback:
backend/tests/test_safety_service.py:23: in <module>
    from app.services.safety_service import SafetyService
E   ModuleNotFoundError: No module named 'app.services.safety_service'
________________ ERROR collecting tests/test_assessment_api.py _________________
ImportError while importing test module '/Users/xingheluqi/XinYu-V2/.worktrees/phase-3-backend-domain-data/backend/tests/test_assessment_api.py'.
Traceback:
backend/tests/test_assessment_api.py:8: in <module>
    from .test_safety_service import build_services, phq9_safety_answers
backend/tests/test_safety_service.py:23: in <module>
    from app.services.safety_service import SafetyService
E   ModuleNotFoundError: No module named 'app.services.safety_service'
=========================== short test summary info ============================
ERROR backend/tests/test_safety_service.py
ERROR backend/tests/test_assessment_api.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
============================== 2 errors in 0.22s ===============================
```

## TDD GREEN

命令：

```bash
backend/.venv/bin/python -m pytest backend/tests/test_safety_service.py backend/tests/test_assessment_api.py
```

实际输出：

```text
============================= test session starts ==============================
platform darwin -- Python 3.11.11, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/xingheluqi/XinYu-V2/.worktrees/phase-3-backend-domain-data/backend
configfile: pyproject.toml
plugins: asyncio-1.2.0, anyio-4.14.2
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 10 items

backend/tests/test_safety_service.py ........                            [ 80%]
backend/tests/test_assessment_api.py ..                                  [100%]

============================== 10 passed in 0.19s ==============================
```

## 测试结果

聚焦回归：

```bash
backend/.venv/bin/python -m pytest backend/tests/test_assessment_service.py backend/tests/test_assessment_rules.py
```

```text
collected 35 items
backend/tests/test_assessment_service.py ............                    [ 34%]
backend/tests/test_assessment_rules.py .......................           [100%]
============================== 35 passed in 0.06s ==============================
```

提交前完整验证：

```bash
backend/.venv/bin/python -m pytest backend/tests
backend/.venv/bin/python -m ruff check backend/app backend/tests
backend/.venv/bin/python -m ruff format --check backend/app backend/tests
backend/.venv/bin/python -m mypy backend/app backend/tests
backend/.venv/bin/python -m compileall -q backend/app backend/tests
```

实际输出摘要：

```text
133 passed in 0.52s
All checks passed!
58 files already formatted
Success: no issues found in 58 source files
compileall exit code 0
```

## 自审

- 响应维度：安全确认响应的 `next_step` 只返回 `continue_assessment`、`show_support_resources`、`support_only`；`result_id` 固定为 null；投影不含 score、完整答案、历史、AI、身份字段或资源敏感目标。资源确认响应只返回 `resource_version`、`acknowledged_at` 和新版本。
- 会话维度：安全确认前和确认请求内的部分答案不持久化；`can_be_safe` 只记录最小确认状态；`uncertain` 资源确认只记录服务端当前资源版本和时间；`cannot_be_safe` 标记 `abandoned` 且不保存答案。
- 结果维度：普通/较高分数结果路径保持原评分服务职责；`uncertain` 完整提交后只保存 `safety_support` 受限结果，`answers_snapshot`、`score`、`reference_band`、`ai_assist_snapshot_id` 均为空；`cannot_be_safe` 不创建 `assessment_results`。
- 任务维度：安全任务只在 `demo` 或 `authorized` 环境创建；`unconfigured` 返回支持路径但不创建 `safety_support_tasks` 或 `work_tasks`。任务初始 `state=needs_action`，不关联 identity record，不写入完整答案、分数或安全确认原文。
- 幂等和并发：安全确认、资源确认、完成流程都使用既有 `IdempotencyService`；重复提交重放同一响应；对象版本不一致返回 `VERSION_CONFLICT`。
- 审计/隐私：审计事实只使用 `AuditWriter` 白名单字段，没有写入安全确认原文、完整答案、身份字段或资源目标。
- API 边界：Pydantic `extra="forbid"` 拒绝客户端传入 `user_id`、`score`、`result_state`、`safety_state`、`environment_id`、`capability` 或任务状态类字段；路由不直接读写数据库或计算分支。

## 疑虑

- `cannot_be_safe` 需要创建安全支持任务，但规范同时要求不创建 `assessment_results` 文档；本实现让任务的 `source_result_id` 使用内部受限引用 `restricted_safety_result:{session_id}`，不落完整结果文档。该处理保持“无完整结果”和“任务可追踪”同时成立，但未来接 CloudBase/后台详情时建议确认是否需要单独的受限安全事实集合。
- `SafetyService` 和 `AssessmentService` 目前各自有一份创建安全任务的最小逻辑，用于避免 3.3 评分职责与 3.4 安全确认互相耦合过深。后续后台任务服务成形时，可抽出专门的任务创建用例以去重。
