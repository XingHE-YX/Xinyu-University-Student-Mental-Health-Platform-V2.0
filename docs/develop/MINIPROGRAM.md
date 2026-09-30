# 学生端开发

微信开发者工具打开 `miniprogram/`，`project.config.json` 的 `miniprogramRoot`
为 `src/`。应用初始化、日志配置、`App(...)` 注册和全局异常处理都位于 `src/app.ts`。
所有小程序运行文件位于 `src/`，测试和 npm 开发依赖位于项目根目录。

## 目录与依赖

```text
miniprogram/
  project.config.json
  package.json
  package-lock.json
  tsconfig.json
  src/
    app.ts
    app.json
    app.wxss
    sitemap.json
    assets/tabbar/
    ui/
      shared/styles/global.wxss
      shared/scripts/display-time.ts
      shared/scripts/page-error.ts
      components/<component>/index.{ts,json,wxml,wxss}
      pages/<page>/index.{ts,json,wxml,wxss}
    services/
      auth.ts
      assessment.ts
      today.ts
      mood.ts
      treehole.ts
      me.ts
      normalizers.ts
    infra/
      config/{runtime,deployment-profiles,local-preview}.ts
      store/{session,assessment}.ts
      types/api.ts
      http.ts
      date.ts
      error.ts
      logger.ts
  tests/
    ui/
    business/
    utils/
    helpers/
```

页面负责交互和视图状态，服务负责业务请求编排及投影转换，基础设施负责网络、
配置、状态、通用类型和工具。页面可读取必要的 store；组件通过 properties 和 events
交互。`infra` 不导入 `services` 或 `ui`；业务服务不导入 UI 工具。
源码使用相对导入，微信路由和组件路径分别以 `/ui/pages/`、`/ui/components/` 开头。
本地覆盖配置使用被 Git 忽略的 `src/ext.json`。

## 样式

`ui/shared/styles/` 只包含所有页面通用的设计令牌、基础字体、背景和 `app-page`
布局，由 `app.wxss` 导入。页面标题、业务列表、表单、弹层和局部状态样式存放在
所属页面或组件的 `index.wxss`，即使部分页面外观相同，也不放入全局样式。
组件应完整提供自身样式，不依赖父页面选择器穿透微信组件隔离边界。

Class 使用小写 kebab-case 和 BEM：页面 block 为 `page-<目录名>`，组件 block 为
`<目录名>`，元素为 `block__element`，状态为 `block--modifier` 或
`block__element--modifier`。全页面基础布局为 `app-page`、`app-page--padded`。
例如 `page-today__mood-sheet-error`、`question-option--selected`。
按钮嵌入答题操作行时，由页面 wrapper 管理 flex 布局，并通过 `inline` 属性启用
`primary-button--inline` 内部样式。完整视觉规范见 [前端指南](FRONTEND_GUIDELINES.md)。

## 错误

后端传输契约 `ApiError`、`ApiEnvelope` 位于 `infra/types/api.ts`。
客户端 `AppError extends Error`、错误定义和转换函数位于 `infra/error.ts`。

| 字段 | 内容 |
| --- | --- |
| `name`、`message`、`stack` | 标准 Error 信息；`message` 用于技术诊断 |
| `code`、`category` | 稳定错误码与配置、网络、HTTP、业务、校验、状态、未知分类 |
| `userMessage` | 页面可以展示的提示 |
| `retryable` | 重试是否可能恢复；具体业务决定是否重试 |
| `requestId`、`clientRequestId` | 服务端响应 ID 与客户端发送的请求 ID |
| `statusCode`、`backendCode` | 可选 HTTP 状态与原始后端错误码 |
| `cause`、`context` | 原始异常，以及模块、操作上下文 |

后端业务码逐项映射到客户端分类，未知后端码保留在 `backendCode`，客户端归为
`UNKNOWN_ERROR`。客户端补充 `CONFIGURATION_ERROR`、`TIMEOUT`、`HTTP_ERROR`、
`INVALID_RESPONSE`、`WX_API_ERROR`、`STATE_ERROR`、`UNKNOWN_ERROR`。
默认提示和重试策略集中在 `errorDefinitions`；HTTP 的 408、429、5xx 可标记为可重试。
写请求的重试必须遵守原有幂等键与版本约束。

请求层返回 `ApiResult<T>`，保留后端 envelope 并附带客户端错误、状态及关联 ID。
业务服务通过 `assertApiSuccess` 或 `assertApiData` 检查响应；需要数据时，缺失数据
归为 `INVALID_RESPONSE`，空数组、空字符串、零和 false 仍是有效数据。
业务状态与输入异常显式使用 `AppError`。页面调用 `handlePageError` 获取提示并记录
异常；需要固定页面提示时，先用 `reportPageError` 记录，再设置既有提示。
任意抛出值由 `normalizeError` 归一化，未知技术错误内容不会直接显示给用户。

## 日志与开发审计

`createLogger(scope)` 提供 `debug`、`info`、`warn`、`error`、`audit`。
结构化记录包含时间、级别、诊断/审计类型、模块、事件和白名单上下文。
开发者工具或 `develop` 环境启用 debug，其他环境默认 warn。
`configureLogger` 支持注入输出函数和时钟；默认输出到对应级别的 console。

请求日志包含模板化路由、请求方法、关联 ID、状态、耗时和错误码。
业务审计记录登录、本地会话清理、同意、身份核验、账户状态、心情保存、自测及
树洞操作的成功结果。会话清理成功与服务端退出成功是不同事件；网络失败仍单独记录。
请求体、返回正文、身份和观察内容、token、任意 cause 和原始错误消息不写入日志。
错误日志保留错误码、分类、重试策略及去除消息首行的调用栈。
`logErrorOnce` 按异常对象避免请求层、页面及全局处理重复记录；输出失败不影响业务。
开发审计输出用于开发排查，正式业务审计由后端维护。

## 测试与验证

| 目录 | 断言对象 |
| --- | --- |
| `tests/ui/` | 页面与组件交互、路由、模板、样式归属和命名 |
| `tests/business/` | 服务、请求、响应转换、业务状态和应用启动 |
| `tests/utils/` | 日期与展示格式、配置、错误和日志工具 |
| `tests/helpers/` | TypeScript 加载器和隔离的微信 mock |

在 `miniprogram/` 执行 `npm run typecheck`、`npm test`。
单类命令为 `npm run test:ui`、`npm run test:business`、`npm run test:utils`；
`npm run test:structure` 仅执行目录、页面、样式和依赖方向检查。
测试只使用本地 mock，提交前在仓库根目录执行 `git diff --check`。
Node 的 TypeScript 加载器使用类型擦除，类型验证由单独的 typecheck 完成。
自动测试不替代微信开发者工具和真机上的编译、样式隔离、交互及业务联调验证。
