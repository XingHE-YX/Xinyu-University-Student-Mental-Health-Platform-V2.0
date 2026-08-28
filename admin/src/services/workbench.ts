export interface WorkbenchTaskSection {
  title: "需要我处理" | "等待他人" | "最近处理";
  count: number;
}

export function getEmptyWorkbench(): WorkbenchTaskSection[] {
  return [
    { title: "需要我处理", count: 0 },
    { title: "等待他人", count: 0 },
    { title: "最近处理", count: 0 },
  ];
}
