<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import DesktopWidthNotice from "@/components/DesktopWidthNotice.vue";

const width = ref(typeof window === "undefined" ? 1440 : window.innerWidth);
const blocked = computed(() => width.value < 1280);
const updateWidth = () => {
  width.value = window.innerWidth;
};
onMounted(() => window.addEventListener("resize", updateWidth));
onUnmounted(() => window.removeEventListener("resize", updateWidth));
</script>

<template>
  <DesktopWidthNotice v-if="blocked" :viewport-width="width" />
  <router-view v-else />
</template>
