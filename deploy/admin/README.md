# 后台静态托管（阶段 7.4）

后台是独立的 Vue 3 + Vite SPA。`hosting.template.json` 为演示和真实授权环境
分别登记 HTTPS 根来源、业务 API、构建产物和刷新回退规则；实际域名和 API 地址
只能在被 Git 忽略的环境文件或 CloudBase 控制台填写。

## 构建与检查

在 `admin/` 目录使用 Node.js 22.21.0 / npm 10.9.4：

```text
npm ci --legacy-peer-deps
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
```

构建前注入 `VITE_API_BASE_URL=https://<api-origin>/api/v1` 和
`VITE_ENVIRONMENT_KIND=demo`（真实授权环境使用对应值）。`admin/src/config/runtime.ts`
会拒绝非 HTTPS 或路径不完整的地址，未配置时后台只显示未配置/不可用状态。

## 发布与刷新验证

```text
python3 deploy/admin/validate_hosting.py <ignored-rendered-hosting.json>
```

将 `admin/dist` 分别上传到两个 CloudBase 静态网站托管入口，配置 HTTPS、后端
CORS/会话允许来源和 SPA fallback `/index.html`。验证登录、W-02 三任务区块、
W-03 两栏详情、W-04 异常状态和 W-05 审计/演示重置；直接刷新深层路由不能泄露
受限详情，未授权环境不能读取演示数据。

按 `FRONTEND_GUIDELINES.md` 验收 1440×900；低于 1280px 只显示电脑浏览器提示，
不渲染可操作工作区。后台构建产物独立于小程序包，不将 `admin/dist` 复制到
`miniprogram/`。
