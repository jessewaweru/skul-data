from django.urls import path, include
from skul_data.dashboards.views.parent import ParentDashboardView
from skul_data.dashboards.views.teacher import TeacherDashboardView
from skul_data.dashboards.views.superuser import SuperUserDashboardView


urlpatterns = [
    path(
        "dashboard/superuser/",
        SuperUserDashboardView.as_view(),
        name="superuser-dashboard",
    ),
    path(
        "dashboard/teacher/", TeacherDashboardView.as_view(), name="teacher-dashboard"
    ),
    path("dashboard/parent/", ParentDashboardView.as_view(), name="parent-dashboard"),
]
