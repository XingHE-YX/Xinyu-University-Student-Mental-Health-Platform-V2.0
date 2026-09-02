<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAdminSessionStore } from "@/stores/adminSession";

defineProps<{
  title: string;
}>();
const session = useAdminSessionStore();
const router = useRouter();
const modeLabel = computed(() => {
  if (session.environmentKind === "authorized") return "授权模式";
  if (session.environmentKind === "unconfigured") return "未配置";
  return "演示模式";
});
const expiresLabel = computed(() =>
  session.sessionExpiresAt
    ? `会话至 ${new Date(session.sessionExpiresAt).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`
    : "会话状态正常",
);

async function signOut(): Promise<void> {
  await session.logout();
  await router.push("/login");
}
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-shell__sidebar" aria-label="后台主导航">
      <div class="admin-shell__brand">
        <span class="admin-shell__brand-name">心语 V2</span>
        <span class="admin-shell__brand-caption">心理健康中心工作台</span>
      </div>
      <nav class="admin-shell__nav">
        <RouterLink class="admin-shell__nav-item" to="/">工作台</RouterLink>
        <RouterLink class="admin-shell__nav-item" to="/audit"
          >审计与演示</RouterLink
        >
        <button
          class="admin-shell__nav-item admin-shell__logout"
          type="button"
          @click="signOut"
        >
          退出登录
        </button>
      </nav>
    </aside>

    <main class="admin-shell__main">
      <header class="admin-shell__header">
        <div>
          <p class="admin-shell__eyebrow">
            {{ session.displayName }} · {{ session.capabilityLabel }}
          </p>
          <h1>{{ title }}</h1>
        </div>
        <span class="admin-shell__session"
          >{{ modeLabel }} · {{ expiresLabel }}</span
        >
      </header>
      <slot />
    </main>
  </div>
</template>

<style scoped>
.admin-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-height: 100vh;
}

.admin-shell__sidebar {
  padding: var(--xinyu-space-10) var(--xinyu-space-6);
  border-right: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
}

.admin-shell__brand {
  display: grid;
  gap: var(--xinyu-space-1);
}

.admin-shell__brand-name {
  font-size: 24px;
  font-weight: 600;
}

.admin-shell__brand-caption,
.admin-shell__eyebrow {
  color: var(--xinyu-color-text-secondary);
  font-size: 12px;
  line-height: 18px;
}

.admin-shell__nav {
  display: grid;
  gap: var(--xinyu-space-2);
  margin-top: var(--xinyu-space-12);
}

.admin-shell__nav-item {
  min-height: 44px;
  padding: var(--xinyu-space-3) var(--xinyu-space-4);
  border-radius: var(--xinyu-radius-md);
  color: var(--xinyu-color-text-secondary);
  text-decoration: none;
}

.admin-shell__nav-item.router-link-active {
  background: var(--xinyu-color-primary-soft);
  color: var(--xinyu-color-primary-pressed);
  font-weight: 600;
}

.admin-shell__logout {
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.admin-shell__main {
  min-width: 0;
  padding: var(--xinyu-space-10);
}

.admin-shell__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--xinyu-space-6);
  margin-bottom: var(--xinyu-space-8);
}

.admin-shell__eyebrow,
h1 {
  margin: 0;
}

h1 {
  margin-top: var(--xinyu-space-2);
  font-size: 28px;
  line-height: 38px;
  font-weight: 600;
}

.admin-shell__session {
  padding: var(--xinyu-space-2) var(--xinyu-space-3);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-sm);
  color: var(--xinyu-color-text-secondary);
  font-size: 14px;
}
</style>
