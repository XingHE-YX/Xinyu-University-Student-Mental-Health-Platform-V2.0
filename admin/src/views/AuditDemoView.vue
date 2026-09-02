<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import AdminShell from "@/components/AdminShell.vue";
import DesktopWidthNotice from "@/components/DesktopWidthNotice.vue";
import AuditTable from "@/components/AuditTable.vue";
import DemoResetDialog from "@/components/DemoResetDialog.vue";
import {
  getAuditEvents,
  resetDemoData,
  type AuditEvent,
  type AuditFilters,
} from "@/services/audit";
import { useAdminSessionStore } from "@/stores/adminSession";

const filters = ref<AuditFilters>({
  eventType: "全部",
  result: "全部",
  mode: "全部",
  objectId: "",
});
const events = ref<AuditEvent[]>([]);
const selected = ref<AuditEvent>();
const page = ref(1);
const total = ref(0);
const requestId = ref("");
const resetOpen = ref(false);
const resetBusy = ref(false);
const resetError = ref("");
const resetMessage = ref("");
const session = useAdminSessionStore();
const loading = ref(false);
const loadError = ref("");
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / 8)));
async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    const result = await getAuditEvents(
      filters.value,
      page.value,
      8,
      session.environmentKind,
    );
    events.value = result.items;
    total.value = result.total;
    requestId.value = result.requestId;
    selected.value = events.value[0];
  } catch {
    selected.value = undefined;
    loadError.value = "暂时没有加载到审计记录，请重新尝试";
  } finally {
    loading.value = false;
  }
}
function applyFilters() {
  page.value = 1;
  void load();
}
async function confirmReset() {
  resetBusy.value = true;
  resetError.value = "";
  resetMessage.value = "";
  try {
    const result = await resetDemoData({
      environment: "演示环境",
      namespace: "demo-xinyu-v2",
    });
    if (!result.success || result.collections.some((item) => !item.success))
      resetError.value = "演示数据暂时没有完成重置，请重新尝试";
    else {
      resetMessage.value = `已完成重置（${result.requestId}）`;
      resetOpen.value = false;
      await load();
    }
  } catch {
    resetError.value = "演示数据暂时没有完成重置，请重新尝试";
  } finally {
    resetBusy.value = false;
  }
}
watch(page, () => void load());
onMounted(() => void load());
</script>
<template>
  <AdminShell title="审计与演示">
    <DesktopWidthNotice />
    <section class="audit" aria-label="审计日志与演示数据">
      <div class="audit__intro">
        <div>
          <p class="eyebrow">W-05 · 只读回溯</p>
          <h2>审计日志</h2>
          <p>记录必要事实，不包含完整正文、答案、身份或 AI 原始内容。</p>
          <p v-if="requestId" class="request-id">
            本次读取请求编号：{{ requestId }}
          </p>
        </div>
        <button
          v-if="session.environmentKind === 'demo'"
          class="reset"
          type="button"
          @click="resetOpen = true"
        >
          重置演示数据
        </button>
      </div>
      <form class="filters" @submit.prevent="applyFilters">
        <label
          >时间范围<input v-model="filters.from" type="date" /> –
          <input v-model="filters.to" type="date" /></label
        ><label
          >事件类型<select v-model="filters.eventType">
            <option>全部</option>
            <option>登录</option>
            <option>公开</option>
            <option>授权</option>
            <option>跟进</option>
          </select></label
        ><label
          >操作结果<select v-model="filters.result">
            <option>全部</option>
            <option>成功</option>
            <option>失败</option>
            <option>拒绝</option>
            <option>冲突</option>
          </select></label
        ><label
          >模式<select v-model="filters.mode">
            <option>全部</option>
            <option>演示模式</option>
            <option>授权模式</option>
          </select></label
        ><label
          >对象编号<input
            v-model="filters.objectId"
            placeholder="仅支持编号" /></label
        ><button class="primary" type="submit">筛选</button>
      </form>
      <div class="audit__body">
        <div class="audit__list">
          <AuditTable
            :events="loading || loadError ? [] : events"
            :selected-id="selected?.id"
            @select="selected = $event"
          />
          <div v-if="loading" class="list-state">正在加载审计记录…</div>
          <div
            v-else-if="loadError"
            class="list-state list-state--error"
            role="alert"
          >
            <p>{{ loadError }}</p>
            <button type="button" @click="load">重新加载</button>
          </div>
          <div class="pager">
            <button type="button" :disabled="page <= 1" @click="page--">
              上一页</button
            ><span>第 {{ page }} / {{ pageCount }} 页 · 共 {{ total }} 条</span
            ><button
              type="button"
              :disabled="page >= pageCount"
              @click="page++"
            >
              下一页
            </button>
          </div>
        </div>
        <aside class="detail" aria-label="事件详情">
          <template v-if="selected"
            ><p class="eyebrow">事件详情 · {{ selected.requestId }}</p>
            <h3>{{ selected.eventType }} · {{ selected.objectId }}</h3>
            <dl>
              <div>
                <dt>操作者</dt>
                <dd>{{ selected.actor }} / {{ selected.capability }}</dd>
              </div>
              <div>
                <dt>操作动作</dt>
                <dd>{{ selected.action }}</dd>
              </div>
              <div>
                <dt>理由或依据</dt>
                <dd>{{ selected.rationale }}</dd>
              </div>
              <div>
                <dt>读取或改变字段</dt>
                <dd>{{ selected.fields }}</dd>
              </div>
              <div>
                <dt>时间与模式</dt>
                <dd>{{ selected.occurredAt }} · {{ selected.mode }}</dd>
              </div>
              <div>
                <dt>结果</dt>
                <dd>{{ selected.result }}</dd>
              </div>
            </dl>
            <p v-if="selected.modelVersion">
              模型与提示词版本：{{ selected.modelVersion }} /
              {{ selected.promptVersion }}
            </p></template
          >
          <p v-else class="empty">暂时没有符合条件的记录</p>
        </aside>
      </div>
      <p v-if="resetMessage" class="success" role="status">
        {{ resetMessage }}
      </p>
    </section>
    <DemoResetDialog
      :open="resetOpen"
      environment="演示环境"
      namespace="demo-xinyu-v2"
      :busy="resetBusy"
      :error="resetError"
      @cancel="resetOpen = false"
      @confirm="confirmReset"
    />
  </AdminShell>
</template>
<style scoped>
.audit {
  display: grid;
  gap: var(--xinyu-space-6);
}
.audit__intro {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid var(--xinyu-color-divider);
  padding-bottom: var(--xinyu-space-6);
}
.eyebrow {
  margin: 0 0 var(--xinyu-space-2);
  color: var(--xinyu-color-text-secondary);
  font-size: 12px;
}
h2,
h3 {
  margin: 0;
  font-size: 20px;
}
.audit__intro p:not(.eyebrow) {
  margin: var(--xinyu-space-2) 0 0;
  color: var(--xinyu-color-text-secondary);
}
.request-id {
  font-size: 12px;
}
button,
input,
select {
  min-height: 44px;
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-surface);
  padding: 0 var(--xinyu-space-3);
}
button {
  cursor: pointer;
}
.reset {
  color: var(--xinyu-color-safety);
  border-color: var(--xinyu-color-safety);
}
.primary {
  border-color: var(--xinyu-color-primary);
  background: var(--xinyu-color-primary);
  color: var(--xinyu-color-surface);
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xinyu-space-3);
  align-items: end;
  padding: var(--xinyu-space-4);
  background: var(--xinyu-color-surface);
  border: 1px solid var(--xinyu-color-divider);
}
label {
  display: grid;
  gap: 4px;
  color: var(--xinyu-color-text-secondary);
  font-size: 12px;
}
.filters input,
.filters select {
  margin-top: 0;
}
.audit__body {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.8fr);
  gap: var(--xinyu-space-6);
}
.pager {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--xinyu-space-4);
  color: var(--xinyu-color-text-secondary);
  font-size: 14px;
}
.list-state {
  margin-top: var(--xinyu-space-3);
  padding: var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-divider);
  color: var(--xinyu-color-text-secondary);
}
.list-state--error {
  color: var(--xinyu-color-safety);
}
.list-state p {
  margin: 0 0 var(--xinyu-space-3);
}
.list-state button {
  cursor: pointer;
}
.detail {
  min-height: 360px;
  padding: var(--xinyu-space-6);
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
}
.detail h3 {
  margin-bottom: var(--xinyu-space-6);
}
dl {
  margin: 0;
}
dl div {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: var(--xinyu-space-3);
  padding: var(--xinyu-space-3) 0;
  border-bottom: 1px solid var(--xinyu-color-divider);
}
dt {
  color: var(--xinyu-color-text-secondary);
}
dd {
  margin: 0;
}
.empty {
  color: var(--xinyu-color-text-secondary);
}
.success {
  margin: 0;
  padding: var(--xinyu-space-3);
  background: var(--xinyu-color-primary-soft);
  color: var(--xinyu-color-primary-pressed);
}
</style>
