from django.urls import path, include
from skul_data.users.views.parent import ParentCreateView
from skul_data.users.views.teacher import TeacherCreateView
from skul_data.users.views.superuser import SuperUserCreateView
from skul_data.users.views.auth import SchoolRegisterAPIView, SchoolLoginAPIView
from rest_framework.routers import DefaultRouter
from skul_data.users.views.role import RoleViewSet
from skul_data.users.views.role import PermissionViewSet


router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"permissions", PermissionViewSet, basename="permission")


urlpatterns = [
    path(
        "register/superuser/",
        SuperUserCreateView.as_view(),
        name="superuser-register",
    ),
    path("", include(router.urls)),
    path("register/teacher/", TeacherCreateView.as_view(), name="teacher-register"),
    path("register/parent/", ParentCreateView.as_view(), name="parent-register"),
    path("register/", SchoolRegisterAPIView.as_view(), name="school-register"),
    path("login/", SchoolLoginAPIView.as_view(), name="login"),
]
