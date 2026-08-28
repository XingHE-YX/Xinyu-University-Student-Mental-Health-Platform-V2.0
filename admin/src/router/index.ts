import { createRouter, createWebHistory } from "vue-router";
import AdminLoginView from "@/views/AdminLoginView.vue";
import WorkbenchView from "@/views/WorkbenchView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: AdminLoginView },
    { path: "/", component: WorkbenchView },
  ],
});

export default router;
