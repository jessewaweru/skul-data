from django.urls import path, include
from skul_data.users.views.parent import ParentCreateView
from skul_data.users.views.superuser import SuperUserCreateView
from skul_data.users.views.auth import SchoolRegisterAPIView, SchoolLoginAPIView
from rest_framework.routers import DefaultRouter
from skul_data.users.views.role import RoleViewSet
from skul_data.users.views.role import PermissionViewSet
from skul_data.users.views.teacher import (
    TeacherViewSet,
    TeacherWorkloadViewSet,
    TeacherAttendanceViewSet,
    TeacherDocumentViewSet,
)


router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"permissions", PermissionViewSet, basename="permission")
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


urlpatterns = [
    path(
        "register/superuser/",
        SuperUserCreateView.as_view(),
        name="superuser-register",
    ),
    path("", include(router.urls)),
    path("register/parent/", ParentCreateView.as_view(), name="parent-register"),
    path("register/", SchoolRegisterAPIView.as_view(), name="school-register"),
    path("login/", SchoolLoginAPIView.as_view(), name="login"),
]
