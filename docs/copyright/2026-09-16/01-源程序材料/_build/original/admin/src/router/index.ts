import { createRouter, createWebHistory } from "vue-router";
import AdminLoginView from "@/views/AdminLoginView.vue";
import WorkbenchView from "@/views/WorkbenchView.vue";
import TaskDetailView from "@/views/TaskDetailView.vue";
import AuditDemoView from "@/views/AuditDemoView.vue";
import { useAdminSessionStore } from "@/stores/adminSession";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: AdminLoginView, meta: { guestOnly: true } },
    { path: "/", component: WorkbenchView, meta: { requiresAuth: true } },
    {
      path: "/tasks/:taskId",
      component: TaskDetailView,
      meta: { requiresAuth: true },
    },
    { path: "/audit", component: AuditDemoView, meta: { requiresAuth: true } },
  ],
});

router.beforeEach((to) => {
  const session = useAdminSessionStore();
  if (to.meta.requiresAuth && !session.isAuthenticated) return "/login";
  if (to.meta.guestOnly && session.isAuthenticated) return "/";
  return true;
});

export default router;
