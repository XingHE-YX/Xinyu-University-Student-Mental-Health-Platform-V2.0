# 学生端发布（阶段 7.3）

`profile.template.json` 只登记两个环境的非秘密 AppID、CloudBase EnvID 和
HTTPS 业务 API 地址。将它复制到被 Git 忽略的本地文件后替换占位符；不要把
AppSecret、CloudBase API Key、DeepSeek Key 或任何身份/支持资源写进小程序配置。

## 发布前检查

```text
python3 deploy/miniprogram/validate_profile.py <ignored-rendered-profile.json>
```

校验器要求演示和授权的 AppID、EnvID 不同，API 地址使用 HTTPS 并以 `/api/v1`
结尾，且不带查询参数或片段。模板本身可以用
`--allow-placeholders` 做结构检查，但不能作为上传配置。

## 微信开发者工具流程

1. 使用微信开发者工具 `2.01.2510290` 打开 `miniprogram/`，在项目设置填入用户
   提供的目标 AppID；演示构建选择演示 CloudBase 环境。
2. 将本地构建配置中的 API 地址指向对应 Python 业务 API，确认它是 HTTPS；后台
   Web 目录不属于小程序项目，不要把 `admin/dist` 复制到 `miniprogram/`。
3. 编译并依次检查首次使用、今日、自测（含 PHQ-9 第 9 题安全确认）、树洞和我
   的页面；再做一次真机验证以及断网/服务不可用重试验证。
4. 在工具中记录工具版本、实际微信基础库版本、演示环境 ID 和体验版版本号；
   通过“上传”生成待提交版本，后续审核/发布在微信公众平台完成。

没有真实 AppID、EnvID 或已授权 API 时，项目保持未配置状态；游客 AppID 的模拟
API 报错不能当作业务代码通过的证据，也不能用游客配置上传正式版本。
