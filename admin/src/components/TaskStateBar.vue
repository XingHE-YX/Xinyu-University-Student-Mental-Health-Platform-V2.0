<script setup lang="ts">
import type { TaskState } from "@/schemas/api";
defineProps<{ state: TaskState; message?: string }>();
const labels: Record<TaskState, string> = {
  needs_action: "待处理",
  claimed: "已认领",
  waiting_other: "等待他人",
  completed: "已完成",
  cancelled: "已结束",
};
</script>
<template>
  <div class="task-state-bar" :class="`task-state-bar--${state}`" role="status">
    <strong>{{ labels[state] }}</strong
    ><span v-if="message">{{ message }}</span>
  </div>
</template>
<style scoped>
.task-state-bar {
  display: flex;
  align-items: baseline;
  gap: var(--xinyu-space-3);
  padding: var(--xinyu-space-3) var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
  line-height: 22px;
}
.task-state-bar--waiting_other {
  background: var(--xinyu-color-caution-soft);
}
.task-state-bar--completed {
  background: var(--xinyu-color-primary-soft);
}
.task-state-bar span {
  color: var(--xinyu-color-text-secondary);
}
</style>
