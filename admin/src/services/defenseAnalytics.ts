import data from "@/defense-data.json";

export const moduleLabels = {
  phq9: "PHQ-9 情绪观察",
  gad7: "GAD-7 焦虑观察",
  sleep_observation: "睡眠观察",
} as const;

export const riskLabels = {
  low: "低风险",
  elevated: "轻度 / 中度",
  high: "重度筛查提示",
} as const;

export const riskBands = ["low", "elevated", "high"] as const;

export type AssessmentModule = keyof typeof moduleLabels;
export type RiskBand = (typeof riskBands)[number];

interface CaseEvent {
  caseId: string;
  at: string;
}

interface AssessmentEvent extends CaseEvent {
  module: AssessmentModule;
  band: RiskBand | null;
}

interface DefenseData {
  batch: string;
  start: string;
  end: string;
  timezone: string;
  assessments: AssessmentEvent[];
  posts: CaseEvent[];
}

export const defenseData = data as DefenseData;

interface DefenseFilters {
  start: string;
  end: string;
  module: AssessmentModule | "all";
}

interface CaseSummary {
  id: string;
  lastAssessment: string;
  assessments: number;
  posts: number;
  latestByModule: Partial<Record<AssessmentModule, AssessmentEvent>>;
  band: RiskBand | null;
}

const DAY = 86_400_000;

function emptyRisk(): Record<RiskBand, number> {
  return { low: 0, elevated: 0, high: 0 };
}

function dayIndex(date: string) {
  return (
    (Date.parse(`${date}T00:00:00Z`) - Date.parse(`${data.start}T00:00:00Z`)) /
    DAY
  );
}

function dateAt(index: number) {
  return new Date(Date.parse(`${data.start}T00:00:00Z`) + index * DAY)
    .toISOString()
    .slice(0, 10);
}

export function percent(part: number, total: number) {
  return total ? Math.round((part / total) * 100) : 0;
}

export function summarizeDefense(filters: DefenseFilters) {
  const matchesDate = (event: CaseEvent) => {
    const date = event.at.slice(0, 10);
    return filters.start <= date && date <= filters.end;
  };
  const assessments = defenseData.assessments.filter(
    (event) =>
      matchesDate(event) &&
      (filters.module === "all" || filters.module === event.module),
  );
  const posts = defenseData.posts.filter(matchesDate);
  const firstWeek = Math.floor(dayIndex(filters.start) / 7);
  const lastWeek = Math.floor(dayIndex(filters.end) / 7);
  const weeks = Array.from(
    { length: Math.max(0, lastWeek - firstWeek + 1) },
    (_, index) => ({
      start: dateAt((firstWeek + index) * 7),
      assessments: 0,
      posts: 0,
    }),
  );
  const periods = [
    { label: "上午", time: "04:00–11:59", risk: emptyRisk(), count: 0 },
    { label: "下午", time: "12:00–17:59", risk: emptyRisk(), count: 0 },
    { label: "晚间", time: "18:00–22:59", risk: emptyRisk(), count: 0 },
    { label: "深夜", time: "23:00–03:59", risk: emptyRisk(), count: 0 },
  ];
  const cases = new Map<string, CaseSummary>();
  const postCounts = new Map<string, number>();
  const modules = { phq9: 0, gad7: 0, sleep_observation: 0 };
  const weekAt = (event: CaseEvent) =>
    weeks[Math.floor(dayIndex(event.at.slice(0, 10)) / 7) - firstWeek];

  for (const post of posts) {
    weekAt(post).posts++;
    postCounts.set(post.caseId, (postCounts.get(post.caseId) ?? 0) + 1);
  }
  for (const event of assessments) {
    weekAt(event).assessments++;
    modules[event.module]++;
    const entry = cases.get(event.caseId) ?? {
      id: event.caseId,
      lastAssessment: "",
      posts: postCounts.get(event.caseId) ?? 0,
      assessments: 0,
      latestByModule: {},
      band: null,
    };
    entry.assessments++;
    if (event.at > entry.lastAssessment) entry.lastAssessment = event.at;
    const previous = entry.latestByModule[event.module];
    if (!previous || event.at > previous.at)
      entry.latestByModule[event.module] = event;
    cases.set(entry.id, entry);

    if (event.band) {
      const hour = Number(event.at.slice(11, 13));
      const period =
        periods[
          hour < 4 || hour === 23 ? 3 : hour < 12 ? 0 : hour < 18 ? 1 : 2
        ];
      period.risk[event.band]++;
      period.count++;
    }
  }
  const risk = emptyRisk();
  for (const entry of cases.values()) {
    const latest = Object.values(entry.latestByModule).map(
      (event) => event.band,
    );
    entry.band =
      [...riskBands].reverse().find((level) => latest.includes(level)) ?? null;
    if (entry.band) risk[entry.band]++;
  }

  return {
    assessedPeople: cases.size,
    classifiedPeople: risk.low + risk.elevated + risk.high,
    submissions: assessments.length,
    posts: posts.length,
    activeAuthors: postCounts.size,
    weeks,
    periods,
    modules,
    risk,
    cases: [...cases.values()].sort((first, second) =>
      first.id.localeCompare(second.id),
    ),
  };
}
