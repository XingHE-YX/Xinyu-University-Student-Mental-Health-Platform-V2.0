<script setup lang="ts">
import { computed, ref } from "vue";
import type { TaskDetail } from "@/schemas/api";
import type { TaskDecision } from "@/services/taskDetail";
const props = defineProps<{
  task: TaskDetail;
  busy?: boolean;
  readonly?: boolean;
  error?: string | null;
}>();
const emit = defineEmits<{
  claim: [];
  release: [];
  submit: [decision: TaskDecision];
}>();
const selectedAction = ref("");
const reason = ref("");
const factNote = ref("");
const followupDueAt = ref("");
const actionCode = ref("resource_provided");
const isContent = computed(() => props.task.task_kind === "content_review");
const isSupport = computed(() => props.task.task_kind === "safety_support");
const isFollowup = computed(() => props.task.task_kind === "followup");
const canSubmit = computed(() => {
  if (!selectedAction.value) return false;
  if (
    isContent.value &&
    ["unpublish", "safety_review"].includes(selectedAction.value)
  ) {
    return reason.value.trim().length > 0;
  }
  if (
    (isSupport.value || isFollowup.value) &&
    ["record_support", "set_followup", "record_followup", "complete"].includes(
      selectedAction.value,
    )
  ) {
    return factNote.value.trim().length > 0;
  }
  return true;
});
const actionLabels: Record<string, string> = {
  publish: "公开",
  protect: "保护展示",
  unpublish: "暂不公开",
  safety_review: "转安全复核",
  record_support: "确认支持已提供",
  set_followup: "记录一次事实跟进",
  complete: "结束本次支持记录",
  approve: "批准",
  deny: "拒绝",
  revoke: "撤回授权",
  record_followup: "保存跟进记录",
};
function submit(): void {
  if (!selectedAction.value || props.busy || props.readonly) return;
  if (isContent.value)
    emit("submit", {
      action: selectedAction.value as
        "publish" | "protect" | "unpublish" | "safety_review",
      internal_reason: reason.value,
    });
  else if (isSupport.value)
    emit("submit", {
      action: selectedAction.value as
        "record_support" | "set_followup" | "complete",
      fact_note: factNote.value,
      followup_due_at: followupDueAt.value || undefined,
    });
  else if (isFollowup.value)
    emit("submit", {
      action: selectedAction.value as "record_followup" | "complete",
      action_code: actionCode.value,
      fact_note: factNote.value,
      next_due_at: followupDueAt.value || undefined,
    });
  else
    emit("submit", {
      action: selectedAction.value as "approve" | "deny" | "revoke",
    });
}
</script>
<template>
  <section class="action-panel" aria-labelledby="action-title">
    <h2 id="action-title">当前操作</h2>
    <p v-if="readonly" class="readonly-note">
      当前任务仅供查看，不能覆盖最新状态。
    </p>
    <template v-else-if="task.state === 'needs_action'"
      ><p class="helper">
        认领后才可以提交决定。服务端会再次校验权限和对象版本。
      </p>
      <button
        class="primary"
        type="button"
        :disabled="busy"
        @click="emit('claim')"
      >
        {{ busy ? "处理中…" : "开始处理" }}
      </button></template
    >
    <template v-else-if="task.state === 'claimed'"
      ><div class="action-options">
        <label
          v-for="action in task.allowed_actions"
          :key="action"
          class="option"
          ><input
            v-model="selectedAction"
            type="radio"
            name="task-action"
            :value="action"
          /><span>{{ actionLabels[action] ?? action }}</span></label
        >
      </div>
      <label v-if="isContent" class="field"
        >内部事实理由<textarea
          v-model="reason"
          rows="4"
          placeholder="仅用于内部审计，不写诊断或身份判断"
        /></label
      ><label v-if="isSupport || isFollowup" class="field"
        >事实记录<textarea
          v-model="factNote"
          rows="4"
          placeholder="只记录已发生的支持、转交或跟进事实"
        /></label
      ><label v-if="isFollowup" class="field"
        >记录类型<select v-model="actionCode">
          <option value="resource_provided">已提供资源</option>
          <option value="contact_made">已完成经授权的联系</option>
          <option value="contact_failed">未能完成经授权的步骤</option>
          <option value="next_contact_agreed">已约定下一次跟进</option>
        </select></label
      ><label v-if="isSupport || isFollowup" class="field"
        >下一次跟进时间<input v-model="followupDueAt" type="datetime-local"
      /></label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="actions">
        <button
          class="primary"
          type="button"
          :disabled="busy || !canSubmit"
          @click="submit"
        >
          {{ busy ? "提交中…" : "提交决定" }}</button
        ><button type="button" :disabled="busy" @click="emit('release')">
          释放任务
        </button>
      </div></template
    >
    <p v-else class="readonly-note">
      {{
        task.state === "waiting_other"
          ? "这条记录正在等待他人处理。"
          : "这条记录已经完成，页面仅供回看。"
      }}
    </p>
  </section>
</template>
<style scoped>
.action-panel {
  padding-left: var(--xinyu-space-8);
  border-left: 1px solid var(--xinyu-color-divider);
}
h2 {
  margin: 0;
  font-size: 20px;
  line-height: 30px;
}
.helper,
.readonly-note {
  color: var(--xinyu-color-text-secondary);
  line-height: 24px;
}
.action-options {
  display: grid;
  gap: var(--xinyu-space-2);
  margin: var(--xinyu-space-6) 0;
}
.option {
  display: flex;
  align-items: center;
  gap: var(--xinyu-space-3);
  min-height: 44px;
  padding: 0 var(--xinyu-space-3);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
}
.option:has(input:checked) {
  border: 2px solid var(--xinyu-color-primary);
  background: var(--xinyu-color-primary-soft);
}
.field {
  display: grid;
  gap: var(--xinyu-space-2);
  margin-top: var(--xinyu-space-4);
  color: var(--xinyu-color-text-secondary);
  font-size: 14px;
}
textarea,
select,
input[type="datetime-local"] {
  width: 100%;
  padding: var(--xinyu-space-3);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
  color: var(--xinyu-color-text);
  resize: vertical;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xinyu-space-3);
  margin-top: var(--xinyu-space-6);
}
button {
  min-height: 44px;
  padding: 0 var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
  color: var(--xinyu-color-text);
  cursor: pointer;
}
button.primary {
  border-color: var(--xinyu-color-primary);
  background: var(--xinyu-color-primary);
  color: var(--xinyu-color-surface);
}
button:disabled {
  color: var(--xinyu-color-text-muted);
  cursor: not-allowed;
}
.error {
  margin-top: var(--xinyu-space-4);
  color: var(--xinyu-color-safety);
  line-height: 24px;
}
</style>
