import { describe, expect, it } from "vitest";
import { defenseData, percent, summarizeDefense } from "./defenseAnalytics";

const all = {
  start: defenseData.start,
  end: defenseData.end,
  module: "all",
} as const;

describe("defense dashboard", () => {
  it("reconciles document counts, people, trends and the risk denominator", () => {
    const result = summarizeDefense(all);
    expect(result.assessedPeople).toBe(30);
    expect(result.classifiedPeople).toBe(30);
    expect(result.submissions).toBe(495);
    expect(result.posts).toBe(108);
    expect(result.activeAuthors).toBe(30);
    expect(result.risk).toEqual({ low: 15, elevated: 12, high: 3 });
    expect(result.modules).toEqual({
      phq9: 165,
      gad7: 165,
      sleep_observation: 165,
    });
    expect(result.weeks).toHaveLength(13);
    expect(result.weeks.every((week) => week.assessments && week.posts)).toBe(
      true,
    );
    expect(
      result.periods.reduce((total, period) => total + period.count, 0),
    ).toBe(330);
    expect(
      percent(result.periods[3].risk.elevated, result.periods[3].count),
    ).toBeGreaterThan(50);
    expect(
      result.cases.every((item) => item.posts === 3 || item.posts === 4),
    ).toBe(true);
  });

  it("keeps posts date-filtered and excludes sleep questionnaires from severity", () => {
    const sleep = summarizeDefense({ ...all, module: "sleep_observation" });
    expect(sleep.submissions).toBe(165);
    expect(sleep.posts).toBe(108);
    expect(sleep.classifiedPeople).toBe(0);
    expect(sleep.periods.every((period) => period.count === 0)).toBe(true);
    const end = summarizeDefense({ ...all, start: all.end });
    expect(end.submissions).toBeGreaterThan(0);
    expect(end.submissions).toBeLessThan(165);
    expect(end.posts).toBeGreaterThan(0);
    expect(end.posts).toBeLessThan(108);
    expect(end.weeks).toHaveLength(1);
  });
});
