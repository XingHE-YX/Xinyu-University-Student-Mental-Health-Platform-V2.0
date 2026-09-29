<template>
  <div class="state" role="alert">
    <strong>这条记录的状态已经变化，当前页面已只读。</strong
    ><span>请重新读取后再继续。</span>
  </div>
</template>
<style scoped>
.state {
  display: grid;
  gap: 4px;
  padding: var(--xinyu-space-4);
  border: 1px solid var(--xinyu-color-caution);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-caution-soft);
}
.state span {
  color: var(--xinyu-color-text-secondary);
}
</style>
