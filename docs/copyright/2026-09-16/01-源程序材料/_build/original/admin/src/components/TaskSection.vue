<script setup lang="ts">
import TaskCard from "@/components/TaskCard.vue";
import type { TaskSummary, WorkbenchSectionKey } from "@/services/workbench";
defineProps<{
  section: WorkbenchSectionKey;
  title: string;
  tasks: TaskSummary[];
  filtered: boolean;
  loading: boolean;
  error: string | null;
  nextCursor: string | null;
}>();
const emit = defineEmits<{
  retry: [];
  loadMore: [];
  open: [task: TaskSummary];
}>();
</script>
<template>
  <section class="task-section" :aria-labelledby="`section-${section}`">
    <header>
      <h2 :id="`section-${section}`">{{ title }}</h2>
      <span>{{ tasks.length }} 条</span>
    </header>
    <p v-if="loading" class="state">正在加载记录…</p>
    <div v-else-if="error" class="state state--error">
      <p>{{ error }}</p>
      <button type="button" @click="emit('retry')">重新加载</button>
    </div>
    <p v-else-if="tasks.length === 0" class="state">
      {{
        filtered
          ? "当前筛选条件下没有记录"
          : section === "recent"
            ? "暂时没有最近处理的记录"
            : section === "waiting_other"
              ? "暂时没有等待他人的记录"
              : "暂时没有需要你处理的记录"
      }}
    </p>
    <div v-else>
      <TaskCard
        v-for="task in tasks"
        :key="task.task_id"
        :task="task"
        :readonly="section !== 'needs_action'"
        @open="emit('open', $event)"
      /><button
        v-if="nextCursor"
        class="more"
        type="button"
        @click="emit('loadMore')"
      >
        加载更多
      </button>
    </div>
  </section>
</template>
<style scoped>
.task-section {
  min-width: 0;
  padding: 0 var(--xinyu-space-6);
  border-left: 1px solid var(--xinyu-color-divider);
}
.task-section:first-child {
  border-left: 0;
  padding-left: 0;
}
header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xinyu-space-3);
}
h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
header span {
  color: var(--xinyu-color-text-muted);
  font-size: 13px;
}
.state {
  padding: var(--xinyu-space-8) 0;
  color: var(--xinyu-color-text-muted);
  line-height: 24px;
}
.state--error {
  color: var(--xinyu-color-safety);
}
.state p {
  margin: 0 0 var(--xinyu-space-3);
}
.state button,
.more {
  min-height: 44px;
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
  padding: 0 var(--xinyu-space-3);
  border-radius: var(--xinyu-radius-sm);
  color: var(--xinyu-color-primary-pressed);
}
.more {
  margin-top: var(--xinyu-space-4);
  width: 100%;
}
</style>
