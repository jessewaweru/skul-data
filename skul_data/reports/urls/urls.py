from django.urls import path
from rest_framework.routers import DefaultRouter
from skul_data.reports.views.report import (
    ReportTemplateViewSet,
    GeneratedReportViewSet,
    ReportScheduleViewSet,
    ReportAccessLogViewSet,
    ReportNotificationViewSet,
    AcademicReportConfigViewSet,
    TermReportRequestViewSet,
    AcademicReportViewSet,
)
from skul_data.reports.views.academic_record import (
    TeacherCommentViewSet,
    AcademicRecordViewSet,
)

router = DefaultRouter()
router.register(r"templates", ReportTemplateViewSet, basename="report-template")
router.register(r"generated", GeneratedReportViewSet, basename="generated-report")
router.register(r"schedules", ReportScheduleViewSet, basename="report-schedule")
router.register(r"access-logs", ReportAccessLogViewSet, basename="report-access-log")
router.register(
    r"notifications", ReportNotificationViewSet, basename="report-notification"
)
router.register(
    r"academic-config", AcademicReportConfigViewSet, basename="academic-report-config"
)
router.register(
    r"term-requests", TermReportRequestViewSet, basename="term-report-request"
)
router.register(r"academic-reports", AcademicReportViewSet, basename="academic-report")
router.register(r"teacher-comments", TeacherCommentViewSet, basename="teacher-comment")
router.register(r"academic-records", AcademicRecordViewSet, basename="academic-record")

urlpatterns = router.urls + [
    path(
        "academic/",
        AcademicReportViewSet.as_view({"post": "generate_term_reports"}),
        name="academic-reports",
    ),
    # Additional custom endpoints can be added here
]
