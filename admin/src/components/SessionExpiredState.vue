<script setup lang="ts">
defineEmits<{ login: [] }>();
</script>
<template>
  <div class="state" role="alert">
    <strong>登录状态已过期，请重新登录。</strong
    ><button type="button" @click="$emit('login')">返回登录</button>
  </div>
</template>
<style scoped>
.state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xinyu-space-4);
  padding: var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-caution);
  background: var(--xinyu-color-caution-soft);
}
button {
  min-height: 44px;
  padding: 0 var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-primary);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-primary);
  color: var(--xinyu-color-surface);
}
</style>
