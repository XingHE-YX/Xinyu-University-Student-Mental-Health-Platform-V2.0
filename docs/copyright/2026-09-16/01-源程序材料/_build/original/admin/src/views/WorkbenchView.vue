<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import AdminShell from "@/components/AdminShell.vue";
import DesktopWidthNotice from "@/components/DesktopWidthNotice.vue";
import TaskSection from "@/components/TaskSection.vue";
import {
  fetchWorkbenchSection,
  WORKBENCH_SECTIONS,
  type TaskSummary,
  type WorkbenchSectionKey,
} from "@/services/workbench";
import type { TaskKind, TaskState } from "@/schemas/api";
import { useAdminSessionStore } from "@/stores/adminSession";
import { AdminApiError } from "@/services/apiClient";
type SectionState = {
  tasks: TaskSummary[];
  loading: boolean;
  error: string | null;
  nextCursor: string | null;
};
const titles: Record<WorkbenchSectionKey, string> = {
  needs_action: "需要我处理",
  waiting_other: "等待他人",
  recent: "最近处理",
};
const router = useRouter();
const session = useAdminSessionStore();
const filterKind = ref<"all" | TaskKind>("all");
const filterState = ref<"all" | TaskState>("all");
const filterSince = ref("");
const hasFilter = computed(
  () =>
    filterKind.value !== "all" ||
    filterState.value !== "all" ||
    !!filterSince.value,
);
const states = reactive<Record<WorkbenchSectionKey, SectionState>>(
  Object.fromEntries(
    WORKBENCH_SECTIONS.map((key) => [
      key,
      { tasks: [], loading: false, error: null, nextCursor: null },
    ]),
  ) as Record<WorkbenchSectionKey, SectionState>,
);
async function load(key: WorkbenchSectionKey, append = false) {
  const state = states[key];
  state.loading = true;
  state.error = null;
  try {
    const page = await fetchWorkbenchSection(
      key,
      append ? state.nextCursor : null,
      fetch,
      session.accessToken,
    );
    state.tasks = append ? [...state.tasks, ...page.items] : page.items;
    state.nextCursor = page.next_cursor;
  } catch (error) {
    if (
      error instanceof AdminApiError &&
      (error.status === 401 || error.code === "SESSION_EXPIRED")
    ) {
      session.clear();
      void router.push("/login");
      return;
    }
    state.error = "暂时没有加载到任务，请重新尝试";
  } finally {
    state.loading = false;
  }
}
function openTask(task: TaskSummary) {
  void router.push(`/tasks/${encodeURIComponent(task.task_id)}`);
}
function visibleTasks(key: WorkbenchSectionKey): TaskSummary[] {
  return states[key].tasks.filter((task) => {
    if (filterKind.value !== "all" && task.task_kind !== filterKind.value)
      return false;
    if (filterState.value !== "all" && task.state !== filterState.value)
      return false;
    if (filterSince.value && task.updated_at.slice(0, 10) < filterSince.value)
      return false;
    return true;
  });
}
onMounted(() => WORKBENCH_SECTIONS.forEach((key) => void load(key)));
</script>
<template>
  <AdminShell title="统一任务工作台"
    ><DesktopWidthNotice />
    <section class="workbench" aria-label="统一任务工作台内容">
      <div class="workbench__intro">
        <p class="workbench__title">当前工作台</p>
        <p class="workbench__description">
          按任务状态查看当前账号可见的最小工作摘要。打开记录后可继续处理或查看已完成事实。
        </p>
      </div>
      <form class="workbench__filters" aria-label="任务筛选">
        <label
          >任务类型<select v-model="filterKind">
            <option value="all">全部任务</option>
            <option value="content_review">内容审核</option>
            <option value="safety_support">安全支持</option>
            <option value="identity_access">身份授权</option>
            <option value="followup">跟进记录</option>
          </select></label
        >
        <label
          >状态<select v-model="filterState">
            <option value="all">全部状态</option>
            <option value="needs_action">待处理</option>
            <option value="claimed">处理中</option>
            <option value="waiting_other">等待他人</option>
            <option value="completed">已完成</option>
          </select></label
        >
        <label>更新时间<input v-model="filterSince" type="date" /></label>
      </form>
      <div class="workbench__sections">
        <TaskSection
          v-for="key in WORKBENCH_SECTIONS"
          :key="key"
          :section="key"
          :title="titles[key]"
          :tasks="visibleTasks(key)"
          :filtered="hasFilter"
          :loading="states[key].loading"
          :error="states[key].error"
          :next-cursor="states[key].nextCursor"
          @retry="load(key)"
          @load-more="load(key, true)"
          @open="openTask"
        />
      </div></section
  ></AdminShell>
</template>
<style scoped>
.workbench {
  display: grid;
  gap: var(--xinyu-space-8);
}
.workbench__intro {
  padding-bottom: var(--xinyu-space-6);
  border-bottom: 1px solid var(--xinyu-color-divider);
}
.workbench__title,
.workbench__description {
  margin: 0;
}
.workbench__title {
  font-size: 20px;
  font-weight: 600;
}
.workbench__description {
  margin-top: var(--xinyu-space-2);
  color: var(--xinyu-color-text-secondary);
  line-height: 26px;
}
.workbench__sections {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xinyu-space-6);
}
.workbench__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: var(--xinyu-space-3);
  padding: var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
}
.workbench__filters label {
  display: grid;
  gap: var(--xinyu-space-1);
  color: var(--xinyu-color-text-secondary);
  font-size: 12px;
}
.workbench__filters select,
.workbench__filters input {
  min-height: 44px;
  min-width: 160px;
  padding: 0 var(--xinyu-space-3);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
  color: var(--xinyu-color-text);
}
@media (max-width: 1279px) {
  .workbench {
    display: none;
  }
}
</style>
