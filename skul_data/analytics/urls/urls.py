from django.urls import path
from rest_framework.routers import DefaultRouter
from skul_data.analytics.views.analytics import (
    AnalyticsViewSet,
    AnalyticsDashboardViewSet,
    AnalyticsAlertViewSet,
)

router = DefaultRouter()
router.register(
    r"dashboards", AnalyticsDashboardViewSet, basename="analytics-dashboard"
)
router.register(r"alerts", AnalyticsAlertViewSet, basename="analytics-alert")

urlpatterns = [
    path(
        "overview/",
        AnalyticsViewSet.as_view({"get": "overview"}),
        name="analytics-overview",
    ),
    path(
        "teachers/",
        AnalyticsViewSet.as_view({"get": "teachers"}),
        name="analytics-teachers",
    ),
    path(
        "students/",
        AnalyticsViewSet.as_view({"get": "students"}),
        name="analytics-students",
    ),
    path(
        "classes/",
        AnalyticsViewSet.as_view({"get": "classes"}),
        name="analytics-classes",
    ),
    path(
        "documents/",
        AnalyticsViewSet.as_view({"get": "documents"}),
        name="analytics-documents",
    ),
    path(
        "reports/",
        AnalyticsViewSet.as_view({"get": "reports"}),
        name="analytics-reports",
    ),
    path(
        "parents/",
        AnalyticsViewSet.as_view({"get": "parents"}),
        name="analytics-parents",
    ),
    path(
        "notifications/",
        AnalyticsViewSet.as_view({"get": "notifications"}),
        name="analytics-notifications",
    ),
    path(
        "school-wide/",
        AnalyticsViewSet.as_view({"get": "school_wide"}),
        name="analytics-school-wide",
    ),
] + router.urls
