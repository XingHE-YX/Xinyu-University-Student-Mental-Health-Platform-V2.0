<template>
  <main class="admin-login">
    <section class="admin-login__panel">
      <p class="admin-login__eyebrow">心语 V2 · 独立桌面管理后台</p>
      <h1>工作人员登录</h1>
      <p>
        初始化阶段仅提供页面入口。固定账号和服务端认证将在后续后端阶段接入。
      </p>
      <RouterLink class="admin-login__link" to="/">进入演示工作台</RouterLink>
    </section>
  </main>
</template>

<style scoped>
.admin-login {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: var(--xinyu-space-10);
}

.admin-login__panel {
  width: min(480px, 100%);
  padding: var(--xinyu-space-8);
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
}

.admin-login__eyebrow {
  color: var(--xinyu-color-text-secondary);
  font-size: 14px;
}

.admin-login h1 {
  margin: var(--xinyu-space-3) 0 0;
  font-size: 28px;
}

.admin-login p {
  line-height: 26px;
}

.admin-login__link {
  display: inline-block;
  margin-top: var(--xinyu-space-4);
  color: var(--xinyu-color-primary);
  font-weight: 600;
}
</style>
