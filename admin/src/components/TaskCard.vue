<script setup lang="ts">
import type { TaskSummary } from "@/services/workbench";
defineProps<{ task: TaskSummary; readonly?: boolean }>();
defineEmits<{ open: [task: TaskSummary] }>();
const kindLabels: Record<TaskSummary["task_kind"], string> = {
  content_review: "内容审核",
  safety_support: "安全支持",
  identity_access: "身份授权",
  followup: "跟进记录",
};
const stateLabels: Record<TaskSummary["state"], string> = {
  needs_action: "待处理",
  claimed: "处理中",
  waiting_other: "等待他人",
  completed: "已完成",
  cancelled: "已结束",
};
</script>
<template>
  <article class="task-card">
    <div class="task-card__meta">
      <span>{{ kindLabels[task.task_kind] }}</span
      ><span>{{ task.task_id }}</span>
    </div>
    <p class="task-card__summary">{{ task.safe_summary }}</p>
    <div class="task-card__footer">
      <span
        >{{ stateLabels[task.state] }} ·
        {{
          new Date(task.updated_at).toLocaleString("zh-CN", {
            dateStyle: "short",
            timeStyle: "short",
          })
        }}</span
      ><button type="button" @click="$emit('open', task)">
        {{ readonly || task.state !== "needs_action" ? "查看" : "开始处理" }}
      </button>
    </div>
  </article>
</template>
<style scoped>
.task-card {
  display: grid;
  gap: var(--xinyu-space-3);
  padding: var(--xinyu-space-4) 0;
  border-bottom: 1px solid var(--xinyu-color-divider);
}
.task-card__meta,
.task-card__footer {
  display: grid;
  grid-template-columns: minmax(100px, auto) minmax(0, 1fr);
  gap: var(--xinyu-space-3);
  align-items: start;
  color: var(--xinyu-color-text-secondary);
  font-size: 13px;
}
.task-card__meta span,
.task-card__footer span {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.task-card__meta span:last-child {
  text-align: right;
}
.task-card__footer {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}
.task-card__summary {
  margin: 0;
  color: var(--xinyu-color-text);
  line-height: 22px;
}
button {
  justify-self: end;
  min-height: 44px;
  padding: 0 var(--xinyu-space-3);
  border: 1px solid var(--xinyu-color-primary);
  border-radius: var(--xinyu-radius-sm);
  background: transparent;
  color: var(--xinyu-color-primary-pressed);
  cursor: pointer;
}
@media (max-width: 760px) {
  .task-card__meta {
    grid-template-columns: 1fr;
  }
  .task-card__meta span:last-child {
    text-align: left;
  }
}
</style>
