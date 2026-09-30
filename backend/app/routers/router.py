"""Single application version prefix and explicit business route registration."""

from fastapi import APIRouter

from app.routers.controller.v2.account import router as account_router
from app.routers.controller.v2.admin.audit import router as admin_audit_router
from app.routers.controller.v2.admin.auth import router as admin_auth_router
from app.routers.controller.v2.admin.demo import router as admin_demo_router
from app.routers.controller.v2.admin.identity_access import router as admin_identity_access_router
from app.routers.controller.v2.admin.workbench import router as admin_workbench_router
from app.routers.controller.v2.assessment import contract_router
from app.routers.controller.v2.assessment import router as assessment_router
from app.routers.controller.v2.auth import router as auth_router
from app.routers.controller.v2.bootstrap import router as bootstrap_router
from app.routers.controller.v2.consent import router as consent_router
from app.routers.controller.v2.health import router as health_router
from app.routers.controller.v2.identity import router as identity_router
from app.routers.controller.v2.me import router as me_router
from app.routers.controller.v2.mood import router as mood_router
from app.routers.controller.v2.support_resource import router as support_resource_router
from app.routers.controller.v2.today import router as today_router
from app.routers.controller.v2.treehole import router as treehole_router
from app.routers.controller.v2.treehole import student_router

router = APIRouter(prefix="/api/v2")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(me_router)
router.include_router(bootstrap_router)
router.include_router(today_router)
router.include_router(mood_router)
router.include_router(consent_router)
router.include_router(identity_router)
router.include_router(assessment_router)
router.include_router(treehole_router)
router.include_router(account_router)
router.include_router(support_resource_router)
router.include_router(admin_auth_router)
router.include_router(admin_workbench_router)
router.include_router(admin_identity_access_router)
router.include_router(admin_audit_router)
router.include_router(admin_demo_router)
router.include_router(contract_router)
router.include_router(student_router)
