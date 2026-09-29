<template>
  <div class="state" role="alert">
    <strong>当前账号无法查看这部分内容。</strong
    ><span>受限事实不会在页面中返回。</span>
  </div>
</template>
<style scoped>
.state {
  display: grid;
  gap: 4px;
  padding: var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-divider);
  background: var(--xinyu-color-surface);
}
.state span {
  color: var(--xinyu-color-text-secondary);
}
</style>
