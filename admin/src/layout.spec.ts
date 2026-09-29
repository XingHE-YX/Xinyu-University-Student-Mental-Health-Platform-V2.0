import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (relativePath: string): string =>
  readFileSync(new URL(relativePath, import.meta.url), "utf8");

describe("responsive admin layout", () => {
  it("contains long task and audit identifiers without hiding the workspace", () => {
    const taskCard = source("./components/TaskCard.vue");
    const auditTable = source("./components/AuditTable.vue");
    const app = source("./App.vue");

    expect(taskCard).toContain("overflow-wrap: anywhere");
    expect(auditTable).toContain("minmax(220px, 1.6fr)");
    expect(auditTable).toContain("overflow-wrap: anywhere");
    expect(app).not.toContain('v-if="blocked"');
  });
});
