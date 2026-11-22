<script setup lang="ts">
import { computed, ref } from "vue";
import AdminShell from "@/components/AdminShell.vue";
import {
  defenseData,
  moduleLabels,
  percent,
  riskBands,
  riskLabels,
  summarizeDefense,
} from "@/services/defenseAnalytics";
import type { AssessmentModule } from "@/services/defenseAnalytics";

const from = ref(defenseData.start);
const to = ref(defenseData.end);
const selected = ref<AssessmentModule | "all">("all");
const invalidDates = computed(
  () =>
    !from.value ||
    !to.value ||
    from.value > to.value ||
    from.value < defenseData.start ||
    to.value > defenseData.end,
);
const stats = computed(() =>
  summarizeDefense({
    start: invalidDates.value ? defenseData.start : from.value,
    end: invalidDates.value ? defenseData.end : to.value,
    module: selected.value,
  }),
);
const deepNight = computed(() => stats.value.periods[3]);
const formatNumber = new Intl.NumberFormat("zh-CN");
const lowPercent = computed(() =>
  percent(stats.value.risk.low, stats.value.classifiedPeople),
);
const elevatedEnd = computed(() =>
  percent(
    stats.value.risk.low + stats.value.risk.elevated,
    stats.value.classifiedPeople,
  ),
);
const donut = computed(() =>
  stats.value.classifiedPeople
    ? `conic-gradient(var(--risk-low) 0% ${lowPercent.value}%, var(--risk-elevated) ${lowPercent.value}% ${elevatedEnd.value}%, var(--risk-high) ${elevatedEnd.value}% 100%)`
    : "var(--defense-track)",
);

const chart = computed(() => {
  const slots = stats.value.weeks;
  const max = Math.max(
    5,
    ...slots.flatMap((week) => [week.assessments, week.posts]),
  );
  const upper = Math.ceil(max / 4) * 4;
  return { upper, ticks: [1, 0.75, 0.5, 0.25, 0] };
});

function resetFilters() {
  from.value = defenseData.start;
  to.value = defenseData.end;
  selected.value = "all";
}
</script>

<template>
  <AdminShell title="答辩数据总览">
    <div class="defense">
      <section class="defense__hero" aria-label="答辩演示说明">
        <div>
          <p class="defense__kicker"><span></span> 答辩演示 · 合成数据</p>
          <h2>学生心理健康观察</h2>
          <p>看参与度、复测和树洞趋势。案例为虚构，筛查结果不构成诊断。</p>
        </div>
        <div class="defense__stamp">
          <strong>2026 秋季学期</strong>
          <span>{{ defenseData.start }} 至 {{ defenseData.end }}</span>
          <span>演示批次 · 北京时间</span>
        </div>
      </section>

      <section class="defense__filters" aria-label="筛选演示数据">
        <label
          >开始日期<input
            v-model="from"
            type="date"
            :min="defenseData.start"
            :max="defenseData.end"
        /></label>
        <label
          >结束日期<input
            v-model="to"
            type="date"
            :min="defenseData.start"
            :max="defenseData.end"
        /></label>
        <label
          >问卷<select v-model="selected">
            <option value="all">全部问卷</option>
            <option
              v-for="(label, module) in moduleLabels"
              :key="module"
              :value="module"
            >
              {{ label }}
            </option>
          </select></label
        >
        <button type="button" @click="resetFilters">重置筛选</button>
      </section>
      <p v-if="invalidDates" class="defense__panel" role="alert">
        请选择演示区间内的有效起止日期。
      </p>

      <template v-else>
        <div class="defense__metrics" aria-label="核心指标" aria-live="polite">
          <article class="defense__metric">
            <p>参与测评</p>
            <strong>{{ stats.assessedPeople }}</strong
            ><span>个去重的合成案例</span>
          </article>
          <article class="defense__metric">
            <p>问卷提交</p>
            <strong>{{ formatNumber.format(stats.submissions) }}</strong
            ><span>份已完成测评，含复测</span>
          </article>
          <article class="defense__metric">
            <p>树洞发帖</p>
            <strong>{{ stats.posts }}</strong
            ><span>{{ stats.activeAuthors }} 人发帖 · 仅按日期筛选</span>
          </article>
          <article class="defense__metric defense__metric--accent">
            <p>深夜轻中度占比</p>
            <strong>{{
              deepNight.count
                ? `${percent(deepNight.risk.elevated, deepNight.count)}%`
                : "—"
            }}</strong
            ><span
              >{{ deepNight.risk.elevated }} /
              {{ deepNight.count }} 次有效筛查</span
            >
          </article>
        </div>

        <div class="defense__primary">
          <section class="defense__panel" aria-labelledby="defense-trend">
            <div class="defense__panel-head">
              <div>
                <h2 id="defense-trend">活动时间轴</h2>
                <p>以 8 月 27 日为起点，每 7 天一组</p>
              </div>
              <div class="defense__legend">
                <span
                  ><i
                    class="defense__legend-dot defense__legend-dot--assessment"
                  ></i
                  >问卷</span
                ><span
                  ><i class="defense__legend-dot defense__legend-dot--post"></i
                  >树洞</span
                >
              </div>
            </div>
            <div class="defense__chart-scroll">
              <div
                class="defense__chart"
                :style="{ '--week-count': stats.weeks.length }"
              >
                <div class="defense__chart-grid" aria-hidden="true">
                  <div v-for="tick in chart.ticks" :key="tick">
                    <span>{{ chart.upper * tick }}</span>
                  </div>
                </div>
                <div
                  v-for="week in stats.weeks"
                  :key="week.start"
                  class="defense__week"
                  :title="`${week.start}起：问卷 ${week.assessments} 份、树洞 ${week.posts} 条`"
                >
                  <div class="defense__bars">
                    <span
                      :style="{
                        height: `${(week.assessments / chart.upper) * 100}%`,
                      }"
                    ></span
                    ><span
                      :style="{
                        height: `${(week.posts / chart.upper) * 100}%`,
                      }"
                    ></span>
                  </div>
                  <span class="defense__week-label">{{
                    week.start.slice(5).replace("-", "/")
                  }}</span>
                </div>
              </div>
            </div>
            <details class="defense__details">
              <summary>查看趋势数值</summary>
              <table>
                <thead>
                  <tr>
                    <th scope="col">分组起始</th>
                    <th scope="col">问卷</th>
                    <th scope="col">树洞</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="week in stats.weeks" :key="week.start">
                    <td>{{ week.start }}</td>
                    <td>{{ week.assessments }}</td>
                    <td>{{ week.posts }}</td>
                  </tr>
                </tbody>
              </table>
            </details>
          </section>

          <section class="defense__panel" aria-labelledby="defense-risk">
            <div class="defense__panel-head">
              <div>
                <h2 id="defense-risk">筛查风险分布</h2>
                <p>每人仅计一次，按筛选期内最近测评归类</p>
              </div>
            </div>
            <div
              class="defense__donut"
              :style="{ background: donut }"
              aria-hidden="true"
            >
              <div>
                <strong>{{ stats.classifiedPeople }}</strong
                ><span>纳入分级</span>
              </div>
            </div>
            <div class="defense__risk-list">
              <div v-for="band in riskBands" :key="band">
                <span
                  ><i
                    class="defense__legend-dot"
                    :class="`defense__band--${band}`"
                  ></i
                  >{{ riskLabels[band] }}</span
                ><strong
                  >{{ stats.risk[band] }}
                  <small
                    >人 ·
                    {{
                      percent(stats.risk[band], stats.classifiedPeople)
                    }}%</small
                  ></strong
                >
              </div>
            </div>
            <p class="defense__note">
              {{
                selected === "sleep_observation"
                  ? "睡眠观察不参与风险分级。"
                  : "全部问卷口径取最近一份 PHQ-9 和一份 GAD-7 的较高档，睡眠观察不参与分级。"
              }}
            </p>
          </section>
        </div>

        <div class="defense__secondary">
          <section class="defense__panel" aria-labelledby="defense-periods">
            <div class="defense__panel-head">
              <div>
                <h2 id="defense-periods">分时段筛查</h2>
                <p>按提交次数统计，0 次筛查的时段不计算比例</p>
              </div>
            </div>
            <div
              class="defense__period"
              v-for="period in stats.periods"
              :key="period.label"
            >
              <div>
                <strong>{{ period.label }}</strong
                ><span>{{ period.time }}</span>
              </div>
              <div class="defense__period-track" aria-hidden="true">
                <i
                  v-for="band in riskBands"
                  :key="band"
                  :class="`defense__band--${band}`"
                  :style="{ flexGrow: period.risk[band] }"
                ></i>
              </div>
              <div class="defense__period-count">
                低 {{ period.risk.low }} · 轻中 {{ period.risk.elevated }} · 重
                {{ period.risk.high
                }}<span>{{
                  period.count ? `合计 ${period.count} 次` : "无有效筛查"
                }}</span>
              </div>
            </div>
          </section>

          <section class="defense__panel" aria-labelledby="defense-modules">
            <div class="defense__panel-head">
              <div>
                <h2 id="defense-modules">问卷完成情况</h2>
                <p>区间内每套问卷的提交次数</p>
              </div>
            </div>
            <div
              class="defense__module"
              v-for="(label, module) in moduleLabels"
              :key="module"
            >
              <span>{{ label }}</span
              ><strong>{{ stats.modules[module] }} <small>份</small></strong>
            </div>
            <p class="defense__note">睡眠观察仅计提交次数，不参与风险分级。</p>
          </section>
        </div>

        <section class="defense__panel" aria-labelledby="defense-cases">
          <div class="defense__panel-head">
            <div>
              <h2 id="defense-cases">脱敏案例明细</h2>
              <p>只展示合成案例编号，不展示姓名、学号或原始答案。</p>
            </div>
          </div>
          <details class="defense__details">
            <summary>展开 {{ stats.cases.length }} 个案例</summary>
            <p v-if="!stats.cases.length" class="defense__note">
              这个筛选区间没有测评记录。
            </p>
            <div v-else class="defense__table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">案例</th>
                    <th scope="col">最近测评</th>
                    <th scope="col">问卷</th>
                    <th scope="col">树洞</th>
                    <th scope="col">筛查分级</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in stats.cases" :key="item.id">
                    <td>{{ item.id }}</td>
                    <td>
                      {{ item.lastAssessment.slice(0, 16).replace("T", " ") }}
                    </td>
                    <td>{{ item.assessments }}</td>
                    <td>{{ item.posts }}</td>
                    <td>
                      {{ item.band ? riskLabels[item.band] : "不参与分级" }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </section>
        <p class="defense__note">
          此看板使用答辩批次的脱敏快照，不读取其他学生数据，也不是实时监测或处置工具。
        </p>
      </template>
    </div>
  </AdminShell>
</template>

<style scoped>
.defense {
  --risk-low: #287d73;
  --risk-elevated: #c18537;
  --risk-high: #ba594e;
  --post: #8799c2;
  --defense-track: #e6ece8;
  display: grid;
  gap: 18px;
  max-width: 1440px;
  margin-inline: auto;
}
.defense__hero,
.defense__filters,
.defense__panel,
.defense__metric {
  border-radius: 14px;
}
.defense__hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 28px 32px;
  background: linear-gradient(120deg, #183e3a, #28635a);
  color: #fff;
}
.defense__hero h2 {
  margin: 8px 0;
  font-size: clamp(24px, 3vw, 36px);
}
.defense__hero p {
  margin: 0;
  color: #e0f0e9;
}
.defense__kicker {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.defense__kicker span {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 5px;
  border-radius: 50%;
  background: #aed9bd;
}
.defense__stamp {
  display: grid;
  align-content: center;
  justify-items: end;
  gap: 5px;
  white-space: nowrap;
}
.defense__stamp span {
  font-size: 12px;
  color: #d9ece3;
}
.defense__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
  padding: 16px 20px;
  border: 1px solid var(--xinyu-color-divider);
  background: #fff;
}
.defense__filters label {
  display: grid;
  gap: 5px;
  color: var(--xinyu-color-text-secondary);
  font-size: 12px;
  font-weight: 650;
}
.defense__filters :is(input, select, button) {
  min-height: 38px;
  padding: 5px 10px;
  border: 1px solid var(--xinyu-color-divider);
  border-radius: 7px;
  color: var(--xinyu-color-text);
  background: #fff;
  font: inherit;
  font-size: 14px;
}
.defense__filters button {
  cursor: pointer;
  color: #245b55;
  background: #edf6f0;
}
.defense__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.defense__panel,
.defense__metric {
  min-width: 0;
  border: 1px solid var(--xinyu-color-divider);
  background: #fff;
}
.defense__metric {
  display: grid;
  gap: 3px;
  padding: 15px 18px;
}
.defense__metric p,
.defense__panel p {
  margin: 0;
}
.defense__metric p {
  font-weight: 650;
  color: var(--xinyu-color-text-secondary);
}
.defense__metric strong {
  font-size: 34px;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.defense__metric span,
.defense__note {
  color: var(--xinyu-color-text-secondary);
  font-size: 13px;
}
.defense__metric--accent {
  background: #faf3e5;
  border-color: #e7d6b7;
}
.defense__primary,
.defense__secondary {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(250px, 1fr);
  gap: 14px;
}
.defense__panel {
  padding: 19px 20px;
}
.defense__panel-head {
  display: flex;
  flex-wrap: wrap;
  align-items: start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 14px;
}
.defense__panel-head h2 {
  margin: 0 0 4px;
  font-size: 18px;
}
.defense__panel-head p {
  color: var(--xinyu-color-text-secondary);
  font-size: 13px;
}
.defense__legend,
.defense__legend > span,
.defense__risk-list > div > span {
  display: flex;
  align-items: center;
  gap: 7px;
}
.defense__legend {
  font-size: 12px;
  gap: 12px;
}
.defense__legend-dot {
  display: inline-block;
  flex: none;
  width: 9px;
  height: 9px;
  border-radius: 50%;
}
.defense__legend-dot--assessment,
.defense__band--low {
  background: var(--risk-low);
}
.defense__legend-dot--post {
  background: var(--post);
}
.defense__band--elevated {
  background: var(--risk-elevated);
}
.defense__band--high {
  background: var(--risk-high);
}
.defense__chart-scroll,
.defense__table-scroll {
  overflow-x: auto;
}
.defense__chart {
  position: relative;
  display: grid;
  grid-template-columns: repeat(var(--week-count), minmax(28px, 1fr));
  min-width: max(100%, calc(var(--week-count) * 28px + 34px));
  padding: 10px 0 0 34px;
  isolation: isolate;
}
.defense__chart-grid {
  position: absolute;
  z-index: -1;
  inset: 10px 0 25px 34px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.defense__chart-grid > div {
  position: relative;
  border-top: 1px solid #e5ebe8;
}
.defense__chart-grid > div > span {
  position: absolute;
  right: calc(100% + 6px);
  top: 0;
  transform: translateY(-50%);
  font-size: 10px;
  color: var(--xinyu-color-text-secondary);
}
.defense__week {
  display: grid;
  grid-template-rows: 164px 25px;
  text-align: center;
}
.defense__bars {
  display: flex;
  align-items: end;
  justify-content: center;
  gap: 2px;
}
.defense__bars > span {
  width: 30%;
  max-width: 16px;
  border-radius: 3px 3px 0 0;
  background: var(--risk-low);
}
.defense__bars > span + span {
  background: var(--post);
}
.defense__week-label {
  align-self: center;
  white-space: nowrap;
  color: var(--xinyu-color-text-secondary);
  font-size: 10px;
}
.defense__donut {
  display: grid;
  width: 148px;
  aspect-ratio: 1;
  place-items: center;
  margin: 12px auto;
  border-radius: 50%;
}
.defense__donut > div {
  display: grid;
  width: 112px;
  aspect-ratio: 1;
  place-content: center;
  justify-items: center;
  background: #fff;
  border-radius: 50%;
}
.defense__donut strong {
  font-size: 30px;
  line-height: 1.2;
}
.defense__donut span,
.defense__risk-list small,
.defense__module small {
  font-size: 12px;
  font-weight: 400;
  color: var(--xinyu-color-text-secondary);
}
.defense__risk-list > div,
.defense__module {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 7px;
  padding: 8px 0;
  border-bottom: 1px solid #e5ebe8;
  font-size: 14px;
}
.defense__panel .defense__note {
  margin-top: 10px;
}
.defense__period {
  display: grid;
  grid-template-columns: 112px minmax(40px, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  font-size: 13px;
}
.defense__period span {
  display: block;
  color: var(--xinyu-color-text-secondary);
  font-size: 11px;
}
.defense__period-track {
  display: flex;
  height: 10px;
  overflow: hidden;
  border-radius: 12px;
  background: var(--defense-track);
}
.defense__period-count {
  text-align: right;
}
.defense__details summary {
  width: fit-content;
  margin: 9px 0;
  cursor: pointer;
  color: #255c57;
  font-size: 13px;
}
.defense table {
  width: 100%;
  border-collapse: collapse;
  white-space: nowrap;
  font-size: 13px;
}
.defense :is(th, td) {
  border-bottom: 1px solid #e5ebe8;
  padding: 8px;
  text-align: left;
}
.defense th {
  background: #f0f5f2;
}
@media (max-width: 1170px) {
  .defense__primary,
  .defense__secondary {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 660px) {
  .defense__hero {
    flex-direction: column;
    padding: 20px;
  }
  .defense__stamp {
    justify-items: start;
  }
  .defense__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .defense__period {
    grid-template-columns: 75px minmax(20px, 1fr) auto;
  }
}
</style>
