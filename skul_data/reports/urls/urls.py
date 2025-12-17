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
from skul_data.reports.views.report import (
    generate_reports_for_class,
    check_report_generation_status,
    upload_performance,
    generate_performance_template,
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
    path(
        "generate-performance-template/",
        generate_performance_template,
        name="generate-performance-template",
    ),
    path("upload-performance/", upload_performance, name="upload-performance"),
    path(
        "generate-reports-for-class/",
        generate_reports_for_class,
        name="generate-reports-for-class",
    ),
    path(
        "check-report-status/<str:task_id>/",
        check_report_generation_status,
        name="check-report-status",
    ),
    # Additional custom endpoints can be added here
]
