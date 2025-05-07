from django.urls import path, include
from skul_data.users.views.parent import (
    ParentViewSet,
    ParentNotificationViewSet,
    ParentStatusChangeViewSet,
)
from skul_data.users.views.auth import SchoolRegisterAPIView, SchoolLoginAPIView
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
from skul_data.users.views.school_admin import SchoolAdminViewSet


router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"permissions", PermissionViewSet, basename="permission")
router.register("sessions", UserSessionViewSet, basename="usersession")
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

urlpatterns = [
    path("", include(router.urls)),
    path("register/", SchoolRegisterAPIView.as_view(), name="school-register"),
    path("login/", SchoolLoginAPIView.as_view(), name="login"),
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
