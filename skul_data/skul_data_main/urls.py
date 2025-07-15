from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny


schema_view = get_schema_view(
    openapi.Info(
        title="Skul Data API",
        default_version="v1",
        description="API documentation for Skul Data",
    ),
    public=True,
    permission_classes=[AllowAny],
    authentication_classes=[],
)

urlpatterns = [
    # Swagger/Redoc URLs
    path(
        "swagger<format>/", schema_view.without_ui(cache_timeout=0), name="schema-json"
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    # Admin
    path("admin/", admin.site.urls),
    # API routes with /api/ prefix
    path(
        "api/",
        include(
            [
                # Authentication
                path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
                path(
                    "token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
                ),
                # App routes
                path("users/", include("skul_data.users.urls")),
                path(
                    "schools/",
                    include(("skul_data.schools.urls", "schools"), namespace="schools"),
                ),
                path("students/", include("skul_data.students.urls")),
                path(
                    "scheduler/",
                    include(
                        ("skul_data.scheduler.urls", "scheduler"), namespace="scheduler"
                    ),
                ),
                path(
                    "documents/",
                    include(
                        ("skul_data.documents.urls", "documents"), namespace="documents"
                    ),
                ),
                path("reports/", include("skul_data.reports.urls")),
                path("analytics/", include("skul_data.analytics.urls")),
                path("logs/", include("skul_data.action_logs.urls")),
                path(
                    "school_timetables/",
                    include(
                        ("skul_data.school_timetables.urls", "school_timetables"),
                        namespace="school_timetables",
                    ),
                ),
                path("notifications/", include("skul_data.notifications.urls")),
            ]
        ),
    ),
]
