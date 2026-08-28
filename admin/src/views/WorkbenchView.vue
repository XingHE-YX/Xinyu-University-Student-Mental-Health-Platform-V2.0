<script setup lang="ts">
import AdminShell from "@/components/AdminShell.vue";
import DesktopWidthNotice from "@/components/DesktopWidthNotice.vue";

const taskSections = [
  {
    title: "需要我处理",
    description: "需要当前工作人员查看或采取行动的任务。",
  },
  {
    title: "等待他人",
    description: "已经转入等待状态、暂不需要重复操作的任务。",
  },
  { title: "最近处理", description: "最近完成或发生状态变化的任务记录。" },
];
</script>

<template>
  <AdminShell title="统一任务工作台">
    <DesktopWidthNotice />
    <section class="workbench" aria-label="统一任务工作台内容">
      <div class="workbench__intro">
        <p class="workbench__title">当前工作台</p>
        <p class="workbench__description">
          这里将在后续阶段接入 W-02
          任务数据。初始化阶段只确认页面骨架、桌面宽度和三块固定任务区域。
        </p>
      </div>
      <div class="workbench__sections">
        <article
          v-for="section in taskSections"
          :key="section.title"
          class="task-section"
        >
          <h2>{{ section.title }}</h2>
          <p>{{ section.description }}</p>
          <span class="task-section__empty">暂无演示任务</span>
        </article>
      </div>
    </section>
  </AdminShell>
</template>

<style scoped>
.workbench {
  display: grid;
  gap: var(--xinyu-space-8);
}

.workbench__intro,
.task-section {
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
}

.workbench__intro {
  padding: var(--xinyu-space-6);
}

.workbench__title,
.workbench__description,
.task-section h2,
.task-section p {
  margin: 0;
}

.workbench__title {
  font-size: 20px;
  font-weight: 600;
}

.workbench__description,
.task-section p {
  margin-top: var(--xinyu-space-2);
  color: var(--xinyu-color-text-secondary);
  font-size: 16px;
  line-height: 26px;
}

.workbench__sections {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xinyu-space-6);
}

.task-section {
  min-height: 220px;
  padding: var(--xinyu-space-6);
}

.task-section h2 {
  font-size: 18px;
  line-height: 28px;
  font-weight: 500;
}

.task-section__empty {
  display: block;
  margin-top: var(--xinyu-space-8);
  color: var(--xinyu-color-text-muted);
  font-size: 14px;
}
</style>
