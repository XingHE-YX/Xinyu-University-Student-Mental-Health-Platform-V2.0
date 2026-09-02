# Task 2 学生核心接口交付报告

## 状态

DONE_WITH_CONCERNS

## 改动文件

- `backend/app/api/student_core.py`：初始化、同意、身份、今日、心情、支持资源及账户状态路由。
- `backend/app/services/account_service.py`：账户停止/恢复/状态，含版本校验、幂等记录、事务和审计。
- `backend/app/services/bootstrap_service.py`：按基础同意状态返回安全初始化投影。
- `backend/app/schemas/student_core.py`：学生核心请求与投影模型。
- `backend/app/main.py`：注册学生核心服务与路由（已在 `bc8be21` 中提交）。
- `backend/app/services/auth_service.py`、`identity_service.py`、`repositories/domain_data_repository.py`：认证主体与业务用户绑定、身份查询支持（主体改动已在 `bc8be21`；仓储树洞兼容修复仍由后续任务整合）。
- `backend/app/api/auth.py`：`/me` 读取真实账户状态。
- `backend/tests/test_student_core_api.py`：HTTP 初始化、同意、账户停止/恢复、幂等缺失和状态回读测试。

## TDD 证据

- RED：新增 HTTP 测试首次运行失败：`/api/v1/app/bootstrap` 与 `/api/v1/account/stop` 返回 404。
- GREEN：实现路由、服务和应用装配后，目标分层测试通过：`63 passed`。
- Ruff 对本任务变更文件通过；mypy 对账户、初始化、学生核心路由和 schema 通过。

## 自审

- 写操作均经过 `Idempotency-Key`，账户状态写入使用事务和对象版本，并在成功后写最小审计事实。
- 初始化在未完成基础同意时不调用私密今日投影；身份查询仅返回状态与轮询信息，不返回姓名或学号。
- 支持资源路由限定学生主体；`/me` 不再硬编码 active。

## 疑虑

- 真实 CloudBase、微信 AppID、域名及授权凭据仍未配置，按任务要求未处理。
- 当前工作区有其他任务并行修改的 assessment/treehole 文件；本报告提交仅包含本任务增量，最终整合需继续运行全量门禁。

## 提交

- `bc8be21 feat: expose student core API contract`
- `c6895a2 fix: harden student core account and access flows`
