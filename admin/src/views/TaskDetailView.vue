<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import AdminShell from "@/components/AdminShell.vue";
import TaskFactsPanel from "@/components/TaskFactsPanel.vue";
import TaskActionPanel from "@/components/TaskActionPanel.vue";
import TaskStateBar from "@/components/TaskStateBar.vue";
import ConcurrencyState from "@/components/ConcurrencyState.vue";
import PermissionState from "@/components/PermissionState.vue";
import SessionExpiredState from "@/components/SessionExpiredState.vue";
import SubmitFailureState from "@/components/SubmitFailureState.vue";
import { AdminApiError } from "@/services/apiClient";
import {
  claimTask,
  decideTask,
  fetchTaskDetail,
  releaseTask,
  type TaskMutationResult,
  type TaskDecision,
} from "@/services/taskDetail";
import { useAdminSessionStore } from "@/stores/adminSession";
import type { TaskDetail } from "@/schemas/api";

const route = useRoute();
const router = useRouter();
const session = useAdminSessionStore();
const task = ref<TaskDetail>();
const loading = ref(true);
const loadError = ref("");
const conflict = ref(false);
const permissionDenied = ref(false);
const expired = ref(false);
const submitError = ref(false);
const busy = ref(false);

const taskLabels = {
  content_review: "内容审核",
  safety_support: "安全支持",
  identity_access: "身份授权",
  followup: "跟进记录",
} as const;

async function load(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  permissionDenied.value = false;
  conflict.value = false;
  expired.value = false;
  submitError.value = false;
  try {
    task.value = await fetchTaskDetail(
      String(route.params.taskId),
      session.accessToken,
    );
  } catch (error) {
    handleError(error, true);
  } finally {
    loading.value = false;
  }
}

function handleError(error: unknown, duringLoad = false): void {
  if (!(error instanceof AdminApiError)) {
    if (duringLoad) loadError.value = "暂时没有加载到任务，请重新尝试";
    else submitError.value = true;
    return;
  }
  if (error.code === "SESSION_EXPIRED" || error.status === 401) {
    expired.value = true;
    task.value = undefined;
    session.clear();
    return;
  }
  if (error.code === "FORBIDDEN" || error.status === 403) {
    permissionDenied.value = true;
    return;
  }
  if (error.code === "VERSION_CONFLICT" || error.status === 409) {
    conflict.value = true;
    return;
  }
  if (duringLoad) loadError.value = error.message;
  else submitError.value = true;
}

async function claim(): Promise<void> {
  if (!task.value) return;
  await mutate(() =>
    claimTask(
      task.value!.task_id,
      task.value!.object_version,
      session.accessToken,
    ),
  );
}
async function release(): Promise<void> {
  if (!task.value) return;
  await mutate(() =>
    releaseTask(
      task.value!.task_id,
      task.value!.object_version,
      session.accessToken,
    ),
  );
}
async function submit(decision: TaskDecision): Promise<void> {
  if (!task.value) return;
  submitError.value = false;
  await mutate(() =>
    decideTask(
      task.value!.task_id,
      task.value!.object_version,
      decision,
      session.accessToken,
    ),
  );
}
async function mutate(
  action: () => Promise<TaskMutationResult>,
): Promise<void> {
  busy.value = true;
  try {
    await action();
    await load();
  } catch (error) {
    handleError(error);
  } finally {
    busy.value = false;
  }
}
function goLogin(): void {
  void router.push("/login");
}
function goBack(): void {
  void router.push("/");
}
onMounted(() => void load());
</script>

<template>
  <AdminShell
    :title="
      task ? `${taskLabels[task.task_kind]} · ${task.task_id}` : '任务详情'
    "
  >
    <section class="task-detail" aria-label="任务详情">
      <div v-if="loading" class="state-message">正在加载必要事实…</div>
      <template v-else-if="expired"
        ><SessionExpiredState @login="goLogin"
      /></template>
      <template v-else-if="permissionDenied"><PermissionState /></template>
      <template v-else-if="loadError"
        ><div class="state-message state-message--error" role="alert">
          <p>{{ loadError }}</p>
          <button type="button" @click="load">重新加载</button>
        </div></template
      >
      <template v-else-if="!task"
        ><div class="state-message">暂时没有找到这条记录。</div></template
      >
      <template v-else>
        <div class="task-detail__top">
          <div>
            <p class="eyebrow">W-03 · {{ taskLabels[task.task_kind] }}</p>
            <h2>{{ task.task_id }}</h2>
          </div>
          <button type="button" @click="goBack">返回工作台</button>
        </div>
        <ConcurrencyState v-if="conflict" />
        <SubmitFailureState v-if="submitError && !conflict" />
        <TaskStateBar
          :state="task.state"
          :message="task.environment_kind === 'demo' ? '演示模式' : '授权模式'"
        />
        <div class="task-detail__columns">
          <TaskFactsPanel :task="task" /><TaskActionPanel
            :task="task"
            :busy="busy"
            :readonly="
              conflict ||
              (task.state !== 'claimed' && task.state !== 'needs_action')
            "
            :error="submitError ? '暂时没有提交成功，请确认后重试' : null"
            @claim="claim"
            @release="release"
            @submit="submit"
          />
        </div>
      </template>
    </section>
  </AdminShell>
</template>

<style scoped>
.task-detail {
  display: grid;
  gap: var(--xinyu-space-6);
}
.state-message {
  padding: var(--xinyu-space-8);
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
  color: var(--xinyu-color-text-secondary);
  line-height: 26px;
}
.state-message p {
  margin: 0 0 var(--xinyu-space-3);
}
.state-message button,
.task-detail__top button {
  min-height: 44px;
  padding: 0 var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
  cursor: pointer;
}
.state-message--error {
  color: var(--xinyu-color-safety);
}
.task-detail__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--xinyu-space-4);
  padding-bottom: var(--xinyu-space-6);
  border-bottom: 1px solid var(--xinyu-color-divider);
}
.eyebrow {
  margin: 0 0 var(--xinyu-space-2);
  color: var(--xinyu-color-text-secondary);
  font-size: 12px;
}
.task-detail h2 {
  margin: 0;
  font-size: 24px;
  line-height: 34px;
}
.task-detail__columns {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 0.85fr);
  gap: var(--xinyu-space-8);
  padding-top: var(--xinyu-space-2);
}
@media (max-width: 1279px) {
  .task-detail {
    display: none;
  }
}
</style>
