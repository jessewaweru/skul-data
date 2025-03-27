from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("skul_data.users.urls")),
    path("schools/", include("skul_data.schools.urls")),
    path("students/", include("skul_data.students.urls")),
    path("documents/", include("skul_data.documents.urls")),
    path("reports/", include("skul_data.reports.urls")),
    path("logs/", include("skul_data.action_logs.urls")),
    path("notifications/", include("skul_data.notifications.urls")),
    path("dashboards/", include("skul_data.dashboards.urls")),
]
