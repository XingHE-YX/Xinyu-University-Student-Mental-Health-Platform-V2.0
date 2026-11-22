// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/vue";
import { describe, expect, it, vi } from "vitest";
import DefenseOverviewView from "./DefenseOverviewView.vue";

vi.mock("@/components/AdminShell.vue", () => ({
  default: {
    props: ["title"],
    template: "<main><h1>{{ title }}</h1><slot /></main>",
  },
}));

describe("defense overview screen", () => {
  it("renders verified analytics and handles filter changes without exposing identities", async () => {
    render(DefenseOverviewView);
    expect(screen.getByRole("heading", { name: "答辩数据总览" })).toBeTruthy();
    expect(screen.getByText("答辩演示 · 合成数据")).toBeTruthy();
    const metrics = within(screen.getByLabelText("核心指标"));
    expect(metrics.getByText("495")).toBeTruthy();
    expect(metrics.getByText("108")).toBeTruthy();
    await fireEvent.update(screen.getByLabelText("问卷"), "sleep_observation");
    expect(metrics.getByText("165")).toBeTruthy();
    expect(screen.getByText("睡眠观察不参与风险分级。")).toBeTruthy();
    await fireEvent.update(screen.getByLabelText("开始日期"), "2026-11-20");
    await fireEvent.update(screen.getByLabelText("结束日期"), "2026-09-01");
    expect(screen.getByRole("alert")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "重置筛选" }));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(
      within(screen.getByLabelText("核心指标")).getByText("495"),
    ).toBeTruthy();
    expect(screen.getByText("展开 30 个案例")).toBeTruthy();
    expect(screen.queryByText(/104253/)).toBeNull();
  });
});
