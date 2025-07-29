from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.exams.views.exam import (
    ExamTypeViewSet,
    GradingSystemViewSet,
    GradeRangeViewSet,
    ExamViewSet,
    ExamSubjectViewSet,
    ExamResultViewSet,
    TermReportViewSet,
)

router = DefaultRouter()
router.register(r"exam-types", ExamTypeViewSet)
router.register(r"grading-systems", GradingSystemViewSet)
router.register(r"grade-ranges", GradeRangeViewSet)
router.register(r"exams", ExamViewSet)
router.register(r"exam-subjects", ExamSubjectViewSet)
router.register(r"exam-results", ExamResultViewSet)
router.register(r"term-reports", TermReportViewSet)

urlpatterns = [
    path("", include(router.urls)),
    # Custom endpoints using existing viewsets
    path("terms/", ExamViewSet.as_view({"get": "terms"}), name="exam-terms-list"),
    path("stats/", ExamViewSet.as_view({"get": "stats"}), name="exam-stats"),
    # Marks upload endpoint (using ExamSubjectViewSet)
    path(
        "exam-subjects/<int:pk>/upload-marks/",
        ExamSubjectViewSet.as_view({"post": "upload_marks"}),
        name="exam-subject-upload-marks",
    ),
    # Analytics endpoints (using ExamViewSet actions)
    path(
        "analytics/performance/",
        ExamViewSet.as_view({"get": "analytics_performance"}),
        name="performance-analytics",
    ),
    path(
        "analytics/subject-trends/",
        ExamViewSet.as_view({"get": "analytics_subject_trends"}),
        name="subject-trends",
    ),
    path(
        "analytics/class-comparison/",
        ExamViewSet.as_view({"get": "analytics_class_comparison"}),
        name="class-comparison",
    ),
]
