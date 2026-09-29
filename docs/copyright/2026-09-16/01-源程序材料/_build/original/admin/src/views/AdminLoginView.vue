<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { AdminApiError } from "@/services/apiClient";
import {
  FIXED_ADMIN_CAPABILITY,
  FIXED_ADMIN_LOGIN,
  loginAdmin,
} from "@/services/adminAuth";
import { useAdminSessionStore } from "@/stores/adminSession";

const router = useRouter();
const session = useAdminSessionStore();
const password = ref("");
const isSubmitting = ref(false);
const errorMessage = ref("");

async function submit(): Promise<void> {
  if (!password.value || isSubmitting.value) return;
  isSubmitting.value = true;
  errorMessage.value = "";
  try {
    session.setSession(await loginAdmin(password.value));
    password.value = "";
    await router.push("/");
  } catch (error) {
    errorMessage.value =
      error instanceof AdminApiError
        ? error.message
        : "暂时无法进入，请重新尝试";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <main class="admin-login">
    <section class="admin-login__panel" aria-labelledby="admin-login-title">
      <p class="admin-login__eyebrow">心语 V2 · 独立桌面管理后台</p>
      <p class="admin-login__mode">演示模式</p>
      <h1 id="admin-login-title">工作人员登录</h1>
      <dl class="admin-login__account">
        <div>
          <dt>账号</dt>
          <dd>{{ FIXED_ADMIN_LOGIN }}</dd>
        </div>
        <div>
          <dt>能力</dt>
          <dd>{{ FIXED_ADMIN_CAPABILITY }}</dd>
        </div>
      </dl>
      <form class="admin-login__form" @submit.prevent="submit">
        <label for="password">登录密码</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
        <p v-if="errorMessage" class="admin-login__error" role="alert">
          {{ errorMessage }}
        </p>
        <button
          class="admin-login__submit"
          type="submit"
          :disabled="isSubmitting || !password"
        >
          {{ isSubmitting ? "正在进入后台，请稍候" : "进入后台" }}
        </button>
      </form>
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
  margin: var(--xinyu-space-2) 0 0;
  font-size: 28px;
}

.admin-login p {
  line-height: 26px;
}

.admin-login__mode {
  margin: var(--xinyu-space-6) 0 0;
  color: var(--xinyu-color-caution);
  font-size: 14px;
  font-weight: 600;
}

.admin-login__account {
  display: grid;
  gap: var(--xinyu-space-2);
  margin: var(--xinyu-space-6) 0 0;
  padding: var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-paper);
}

.admin-login__account div {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: var(--xinyu-space-2);
}

.admin-login__account dt {
  color: var(--xinyu-color-text-secondary);
}

.admin-login__account dd {
  margin: 0;
}

.admin-login__form {
  display: grid;
  gap: var(--xinyu-space-2);
  margin-top: var(--xinyu-space-6);
}

.admin-login__form input {
  min-height: 44px;
  padding: 0 var(--xinyu-space-3);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
}

.admin-login__submit {
  min-height: 44px;
  margin-top: var(--xinyu-space-2);
  border: 0;
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-primary);
  color: var(--xinyu-color-surface);
  cursor: pointer;
}

.admin-login__submit:disabled {
  background: var(--xinyu-color-text-muted);
  cursor: not-allowed;
}

.admin-login__error {
  margin: var(--xinyu-space-2) 0 0;
  color: var(--xinyu-color-safety);
  font-size: 14px;
}
</style>
