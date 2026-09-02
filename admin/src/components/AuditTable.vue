<script setup lang="ts">
import type { AuditEvent } from "@/services/audit";
defineProps<{ events: AuditEvent[]; selectedId?: string }>();
defineEmits<{ select: [event: AuditEvent] }>();
</script>
<template>
  <div class="audit-table" role="table" aria-label="审计日志列表">
    <div class="audit-table__head" role="row">
      <span>时间</span><span>事件</span><span>对象</span><span>操作权限</span
      ><span>结果</span><span>模式</span>
    </div>
    <button
      v-for="event in events"
      :key="event.id"
      class="audit-table__row"
      :class="{ selected: event.id === selectedId }"
      role="row"
      type="button"
      @click="$emit('select', event)"
    >
      <span>{{
        new Date(event.occurredAt).toLocaleString("zh-CN", { hour12: false })
      }}</span
      ><span>{{ event.eventType }}</span
      ><span>{{ event.objectId }}</span
      ><span>{{ event.capability }}</span
      ><span>{{ event.result }}</span
      ><span>{{ event.mode }}</span>
    </button>
    <p v-if="!events.length" class="audit-table__empty">
      暂时没有符合条件的记录
    </p>
  </div>
</template>
<style scoped>
.audit-table {
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
}
.audit-table__head,
.audit-table__row {
  display: grid;
  grid-template-columns: 1.25fr 0.8fr 1.2fr 1fr 0.7fr 0.8fr;
  gap: var(--xinyu-space-3);
  align-items: center;
  padding: 0 var(--xinyu-space-4);
  text-align: left;
}
.audit-table__head {
  min-height: 44px;
  color: var(--xinyu-color-text-secondary);
  font-size: 12px;
  border-bottom: 1px solid var(--xinyu-color-divider);
}
.audit-table__row {
  width: 100%;
  min-height: 56px;
  border: 0;
  border-bottom: 1px solid var(--xinyu-color-divider);
  background: transparent;
  color: var(--xinyu-color-text);
  font-size: 14px;
  cursor: pointer;
}
.audit-table__row:hover,
.audit-table__row.selected {
  background: var(--xinyu-color-primary-soft);
}
.audit-table__empty {
  margin: 0;
  padding: var(--xinyu-space-10);
  color: var(--xinyu-color-text-secondary);
  text-align: center;
}
</style>
