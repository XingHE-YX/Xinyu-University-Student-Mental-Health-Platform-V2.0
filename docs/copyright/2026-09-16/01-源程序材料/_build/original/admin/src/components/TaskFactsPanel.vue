<script setup lang="ts">
import type { TaskDetail } from "@/schemas/api";
defineProps<{ task: TaskDetail }>();
</script>
<template>
  <section class="facts-panel" aria-labelledby="facts-title">
    <h2 id="facts-title">必要事实与脱敏内容</h2>
    <dl>
      <div v-for="fact in task.facts" :key="`${fact.label}-${fact.value}`">
        <dt>{{ fact.label }}</dt>
        <dd>{{ fact.value }}</dd>
      </div>
    </dl>
    <div v-if="task.redacted_content" class="redacted-content">
      <p class="redacted-content__label">已脱敏内容</p>
      <p>{{ task.redacted_content }}</p>
    </div>
    <div v-if="task.records.length" class="records">
      <h3>已发生的事实记录</h3>
      <dl>
        <div
          v-for="record in task.records"
          :key="`${record.label}-${record.value}`"
        >
          <dt>{{ record.label }}</dt>
          <dd>{{ record.value }}</dd>
        </div>
      </dl>
    </div>
  </section>
</template>
<style scoped>
.facts-panel {
  min-width: 0;
}
h2,
h3 {
  margin: 0;
  font-size: 20px;
  line-height: 30px;
  font-weight: 600;
}
dl {
  margin: var(--xinyu-space-6) 0 0;
}
dl div {
  display: grid;
  grid-template-columns: minmax(120px, 0.35fr) 1fr;
  gap: var(--xinyu-space-4);
  padding: var(--xinyu-space-3) 0;
  border-bottom: 1px solid var(--xinyu-color-divider);
}
dt {
  color: var(--xinyu-color-text-secondary);
  font-size: 14px;
}
dd {
  margin: 0;
  line-height: 24px;
  overflow-wrap: anywhere;
}
.redacted-content {
  margin-top: var(--xinyu-space-8);
  padding: var(--xinyu-space-5);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
}
.redacted-content__label {
  margin: 0;
  color: var(--xinyu-color-text-secondary);
  font-size: 12px;
}
.redacted-content p:last-child {
  margin: var(--xinyu-space-3) 0 0;
  white-space: pre-wrap;
  line-height: 26px;
}
.records {
  margin-top: var(--xinyu-space-8);
}
.records dl {
  margin-top: var(--xinyu-space-3);
}
</style>
