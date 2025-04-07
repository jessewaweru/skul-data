from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    # JWT auth
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("users/", include("skul_data.users.urls")),
    path("schools/", include("skul_data.schools.urls")),
    path("students/", include("skul_data.students.urls")),
    path("documents/", include("skul_data.documents.urls")),
    path("reports/", include("skul_data.reports.urls")),
    path("logs/", include("skul_data.action_logs.urls")),
    path("notifications/", include("skul_data.notifications.urls")),
    path("dashboards/", include("skul_data.dashboards.urls")),
]
