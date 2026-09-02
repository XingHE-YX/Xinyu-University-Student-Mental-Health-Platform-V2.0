<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

const props = defineProps<{ viewportWidth?: number }>();
const viewportWidth = ref(
  props.viewportWidth ??
    (typeof window === "undefined" ? 1440 : window.innerWidth),
);
const isBlocked = computed(() => viewportWidth.value < 1280);

function updateViewportWidth(): void {
  viewportWidth.value = window.innerWidth;
}

onMounted(() => window.addEventListener("resize", updateViewportWidth));
onUnmounted(() => window.removeEventListener("resize", updateViewportWidth));
</script>

<template>
  <main v-if="isBlocked" class="desktop-width-notice" aria-live="polite">
    <p class="desktop-width-notice__title">请使用电脑浏览器</p>
    <p class="desktop-width-notice__body">
      当前窗口宽度为 {{ viewportWidth }}px。心语后台的最小工作宽度为
      1280px，请放大窗口后继续。
    </p>
  </main>
</template>

<style scoped>
.desktop-width-notice {
  margin: var(--xinyu-space-10);
  padding: var(--xinyu-space-6);
  border: 1px solid var(--xinyu-color-divider);
  border-radius: var(--xinyu-radius-md);
  background: var(--xinyu-color-caution-soft);
  color: var(--xinyu-color-text);
}

.desktop-width-notice__title,
.desktop-width-notice__body {
  margin: 0;
}

.desktop-width-notice__title {
  font-size: 20px;
  font-weight: 600;
}

.desktop-width-notice__body {
  margin-top: var(--xinyu-space-2);
  color: var(--xinyu-color-text-secondary);
  font-size: 16px;
  line-height: 26px;
}
</style>
