# V2 HTTP 契约完成设计

日期：2026-09-03

## 目标

消除第 12 节完成定义中“后端接口未实现”和“APP_FLOW 成功/错误路径无法由真实 HTTP 复现”的本地阻断。真实 CloudBase、微信 AppID、域名、学校核验和其他授权凭据继续保持未配置，不在本设计范围内。

## 当前问题

`BACKEND_STRUCTURE.md` 当前定义 50 个 `/api/v1` 端点，FastAPI 只注册了 18 个。部分领域服务已经存在，但没有 HTTP 适配器；树洞、账户和后台身份授权也缺少完整服务和内存仓储操作。学生登录目前只创建会话，不保证业务账户存在，因此完整本地链路无法从登录开始执行。

## 设计

### 路由边界

- `backend/app/api/student_core.py`：`app/bootstrap`、同意、`me`、身份核验状态、匿名身份、今日、心情、支持资源、账户停止/恢复/状态。
- `backend/app/api/assessment.py`：保留安全确认和资源确认，增加模块目录、开始、完成、放弃、结果读取/列表/逐条删除。
- `backend/app/api/treehole.py`：公开帖子、发布、详情、我的内容、撤回、删除、回应和回应删除。
- `backend/app/api/admin_identity.py`：后台身份授权申请创建、查询和限定字段读取。

所有路由只做认证依赖、Pydantic 输入校验、服务调用和 `ApiEnvelope` 序列化；不在路由内读写仓储或计算评分。

### 服务和仓储

- `AuthService` 接收领域仓储，微信登录成功后按不可逆主体摘要查找或创建 `UserAccountDocument`。
- 新增 `AccountService`、`BootstrapService`、`TreeholeService` 和 `IdentityAccessService`。
- `AssessmentService` 增加模块摘要、结果投影、结果列表/逻辑删除和会话放弃；结果投影遵守安全支持和睡眠观察边界。
- `InMemoryDomainDataRepository` 增加模块列表、结果删除、树洞帖子/回应、身份授权请求的类型化 CRUD、分页和版本检查。
- 所有写入使用 `IdempotencyService`、对象版本和 `AuditWriter`；失败幂等重放保留完整错误契约。

### 树洞状态和隐私

发布和回应先经过固定格式规则，原文只以受保护值保存；公开接口只返回 `published` 或 `protected` 的 `body_sanitized`。`checking`、`pending_confirmation`、`unpublished`、`safety_priority` 和 `deleted` 只返回作者允许的最小状态，不返回内部理由或其他用户身份。社区同意、基础同意、身份和账户状态由服务端强制检查。

### 后台身份授权

授权申请绑定当前后台主体和服务端读取的 `user_reference_id`，请求字段只能是 `student_name`、`student_number`。批准后在有效期和字段范围内解密读取；每次允许或拒绝读取写最小审计，未经批准不返回身份字段。

## 测试策略

1. 先新增端点注册对照测试，断言规范端点从 18/50 变为 50/50。
2. 每组服务先写失败测试，再实现最小行为，覆盖成功、认证/同意/身份前置条件、版本冲突、幂等重放、逻辑删除和隐私投影。
3. 增加学生端和后台身份授权的 `TestClient` 契约测试，拒绝 `score`、`role`、`safety_state`、`visibility_state`、`environment_id` 等客户端事实字段。
4. 保持现有 166 项后端测试、后台测试和学生端类型检查全部通过，并重新运行端点、隐私、配置和函数包检查。

## 非目标

- 不创建或连接真实 CloudBase 环境，不填写微信 AppID、域名或授权密钥。
- 不引入新的客户端依赖、第三方 UI 库、Node/JavaScript 云函数或客户端 AI 调用。
- 不改变固定量表评分、安全状态机、DeepSeek 降级策略和前端视觉设计令牌。
