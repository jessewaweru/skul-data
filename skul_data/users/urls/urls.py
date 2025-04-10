from django.urls import path
from skul_data.users.views.parent import ParentCreateView
from skul_data.users.views.teacher import TeacherCreateView
from skul_data.users.views.superuser import SuperUserCreateView
from skul_data.users.views.auth import SchoolRegisterAPIView, SchoolLoginAPIView

urlpatterns = [
    path(
        "register/superuser/", SuperUserCreateView.as_view(), name="superuser-register"
    ),
    path("register/teacher/", TeacherCreateView.as_view(), name="teacher-register"),
    path("register/parent/", ParentCreateView.as_view(), name="parent-register"),
    path("register/", SchoolRegisterAPIView.as_view(), name="school-register"),
    path("login/", SchoolLoginAPIView.as_view(), name="login"),
]
