import { describe, expect, it } from "vitest";
import { getEmptyWorkbench } from "./services/workbench";

describe("initial workbench contract", () => {
  it("keeps the three W-02 task sections", () => {
    expect(getEmptyWorkbench().map((section) => section.title)).toEqual([
      "需要我处理",
      "等待他人",
      "最近处理",
    ]);
  });
});
