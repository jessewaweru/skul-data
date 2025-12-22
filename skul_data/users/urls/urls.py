from django.urls import path, include
from skul_data.users.views.parent import (
    ParentViewSet,
    ParentNotificationViewSet,
    ParentStatusChangeViewSet,
)
from skul_data.users.views.auth import (
    SchoolRegisterAPIView,
    SchoolLoginAPIView,
    activate_account,
)
from skul_data.users.views.password_reset import (
    password_reset_request,
    password_reset_verify,
    password_reset_confirm,
    change_password,
    logout_view,
    check_password_strength,
)
from rest_framework.routers import DefaultRouter
from skul_data.users.views.role import RoleViewSet
from skul_data.users.views.role import PermissionViewSet
from skul_data.users.views.session import UserSessionViewSet
from skul_data.users.views.teacher import (
    TeacherViewSet,
    TeacherWorkloadViewSet,
    TeacherAttendanceViewSet,
    TeacherDocumentViewSet,
)
from skul_data.users.views.school_admin import (
    SchoolAdminViewSet,
    AdministratorProfileViewSet,
)
from skul_data.users.views.base_user import UserViewSet

router = DefaultRouter()
router.register(r"", UserViewSet, basename="user")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"permissions", PermissionViewSet, basename="permission")
router.register(r"sessions", UserSessionViewSet, basename="usersession")
router.register(r"teachers", TeacherViewSet, basename="teacher")
router.register(
    r"teacher-workloads", TeacherWorkloadViewSet, basename="teacher-workload"
)
router.register(
    r"teacher-attendances", TeacherAttendanceViewSet, basename="teacher-attendance"
)
router.register(
    r"teacher-documents", TeacherDocumentViewSet, basename="teacher-document"
)
router.register(r"parents", ParentViewSet, basename="parent")
router.register(
    r"parent-notifications", ParentNotificationViewSet, basename="parent-notification"
)
router.register(
    r"parent-status-changes", ParentStatusChangeViewSet, basename="parent-status-change"
)
router.register(r"school-admin", SchoolAdminViewSet, basename="school-admin")
router.register(
    r"administrators", AdministratorProfileViewSet, basename="administrator"
)

urlpatterns = [
    # Authentication endpoints
    path("register/", SchoolRegisterAPIView.as_view(), name="school-register"),
    path("login/", SchoolLoginAPIView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    # Password management endpoints
    path(
        "password-reset/request/", password_reset_request, name="password-reset-request"
    ),
    path("password-reset/verify/", password_reset_verify, name="password-reset-verify"),
    path(
        "password-reset/confirm/", password_reset_confirm, name="password-reset-confirm"
    ),
    path("change-password/", change_password, name="change-password"),
    path(
        "check-password-strength/",
        check_password_strength,
        name="check-password-strength",
    ),
    path("activate-account/<str:token>/", activate_account, name="activate-account"),
    # Router URLs
    path("", include(router.urls)),
    # Custom parent actions
    path(
        "parents/<int:pk>/change-status/",
        ParentViewSet.as_view({"post": "change_status"}),
        name="parent-change-status",
    ),
    path(
        "parents/<int:pk>/assign-children/",
        ParentViewSet.as_view({"post": "assign_children"}),
        name="parent-assign-children",
    ),
    path(
        "parents/<int:pk>/notifications/",
        ParentViewSet.as_view({"get": "notifications"}),
        name="parent-notifications",
    ),
    # Custom teacher actions
    path(
        "teachers/<int:pk>/change-status/",
        TeacherViewSet.as_view({"post": "change_status"}),
        name="teacher-change-status",
    ),
    path(
        "teachers/<int:pk>/assign-subjects/",
        TeacherViewSet.as_view({"post": "assign_subjects"}),
        name="teacher-assign-subjects",
    ),
]
