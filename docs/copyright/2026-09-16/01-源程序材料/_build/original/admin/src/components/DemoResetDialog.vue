<script setup lang="ts">
defineProps<{
  open: boolean;
  environment: string;
  namespace: string;
  busy?: boolean;
  error?: string;
}>();
defineEmits<{ cancel: []; confirm: [] }>();
</script>
<template>
  <div v-if="open" class="dialog-backdrop" role="presentation">
    <section
      class="dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reset-title"
    >
      <h2 id="reset-title">重置演示数据</h2>
      <p>演示数据将恢复到初始案例状态。此操作不会影响真实数据。</p>
      <dl>
        <div>
          <dt>环境</dt>
          <dd>{{ environment }}</dd>
        </div>
        <div>
          <dt>数据范围</dt>
          <dd>{{ namespace }}（任务、帖子、答卷、身份、安全任务与审计）</dd>
        </div>
      </dl>
      <p v-if="error" class="dialog__error" role="alert">{{ error }}</p>
      <div class="dialog__actions">
        <button type="button" @click="$emit('cancel')">取消</button
        ><button
          class="primary"
          type="button"
          :disabled="busy"
          @click="$emit('confirm')"
        >
          {{ busy ? "重置中…" : "确认重置" }}
        </button>
      </div>
    </section>
  </div>
</template>
<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgb(31 45 43 / 25%);
  z-index: 10;
}
.dialog {
  width: min(520px, calc(100vw - 48px));
  padding: var(--xinyu-space-8);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
  box-shadow: 0 8px 24px rgb(31 45 43 / 12%);
}
h2 {
  margin: 0 0 var(--xinyu-space-3);
  font-size: 20px;
}
p {
  color: var(--xinyu-color-text-secondary);
  line-height: 26px;
}
dl {
  margin: var(--xinyu-space-6) 0;
}
dl div {
  display: grid;
  grid-template-columns: 90px 1fr;
  padding: var(--xinyu-space-3) 0;
  border-bottom: 1px solid var(--xinyu-color-divider);
}
dt {
  color: var(--xinyu-color-text-secondary);
}
dd {
  margin: 0;
}
.dialog__error {
  color: var(--xinyu-color-safety);
}
.dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--xinyu-space-3);
}
button {
  min-height: 44px;
  padding: 0 var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
  cursor: pointer;
}
button.primary {
  border-color: var(--xinyu-color-primary);
  background: var(--xinyu-color-primary);
  color: var(--xinyu-color-surface);
}
button:disabled {
  opacity: 0.6;
  cursor: wait;
}
</style>
