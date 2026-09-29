<template>
  <div class="state" role="alert">
    <strong>暂时没有提交成功，请确认后重试。</strong
    ><span>未保存的事实输入仍保留在当前页面。</span>
  </div>
</template>
<style scoped>
.state {
  display: grid;
  gap: 4px;
  padding: var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-safety);
  background: var(--xinyu-color-safety-soft);
}
.state span {
  color: var(--xinyu-color-text-secondary);
}
</style>
