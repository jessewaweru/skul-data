from django.db import models
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.users.permissions.permission import IsAdministrator
from skul_data.analytics.serializers.analytics import (
    AnalyticsAlertSerializer,
    AnalyticsDashboardSerializer,
    AnalyticsFilterSerializer,
)
from skul_data.analytics.models.analytics import (
    AnalyticsDashboard,
    CachedAnalytics,
    AnalyticsAlert,
)
from skul_data.users.models.teacher import Teacher
from skul_data.students.models.student import Student
from skul_data.documents.models.document import Document
from skul_data.analytics.utils.analytics_generator import (
    get_most_active_teacher,
    get_student_attendance_rate,
    get_most_downloaded_document,
    get_top_performing_class,
    get_reports_generated_count,
    get_teacher_logins,
    get_reports_per_teacher,
    get_attendance_accuracy,
    get_student_attendance,
    get_student_performance,
    get_student_dropouts,
    get_class_sizes,
    get_class_average_grades,
    get_top_classes,
    get_class_attendance_rates,
    get_teacher_ratios,
    get_document_download_frequency,
    get_document_types_distribution,
    get_document_access,
    get_document_access_by_role,
    get_uploads_by_user,
    get_reports_generated,
    get_most_accessed_reports,
    get_missing_reports,
    get_top_students_from_reports,
    get_parent_report_views,
    get_most_engaged_parents,
    get_students_per_parent,
    get_parent_feedback,
    get_parent_login_trends,
    get_notification_open_rates,
    get_message_types,
    get_click_through_rates,
    get_unread_notifications,
    get_active_users,
    get_engagement_rates,
    get_report_generation_stats,
    get_school_growth,
    get_teacher_ratios,
    get_document_access_by_role,
    get_document_access_by_role,
    get_uploads_by_user,
    get_response_times,
    get_performance_per_teacher,
)
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.action_logs.models.action_log import ActionLog
from rest_framework import status
from skul_data.users.models.base_user import User


class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdministrator]

    def get_school(self):
        return self.request.user.administered_school

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """Default overview with top 5 metrics"""
        school = self.get_school()

        # Check for cached data first
        cached = CachedAnalytics.objects.filter(
            school=school, analytics_type="overview", valid_until__gte=timezone.now()
        ).first()

        if cached:
            return Response(cached.data)

        # Convert Decimal values to float before caching
        data = {
            "most_active_teacher": (
                dict(get_most_active_teacher(school))
                if get_most_active_teacher(school)
                else None
            ),
            "student_attendance_rate": float(get_student_attendance_rate(school)),
            "most_downloaded_document": (
                dict(get_most_downloaded_document(school))
                if get_most_downloaded_document(school)
                else None
            ),
            "top_performing_class": (
                dict(get_top_performing_class(school))
                if get_top_performing_class(school)
                else None
            ),
            "reports_generated": get_reports_generated_count(school),
        }

        # Cache for 1 hour
        CachedAnalytics.objects.create(
            school=school,
            analytics_type="overview",
            data=data,
            valid_until=timezone.now() + timedelta(hours=1),
        )

        return Response(data)

    @action(detail=False, methods=["get"])
    def teachers(self, request):
        """Teacher-specific analytics"""
        school = self.get_school()
        serializer = AnalyticsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        data = {
            "total_teachers": Teacher.objects.filter(school=school).count(),
            "logins": get_teacher_logins(school, filters),
            "reports_per_teacher": get_reports_per_teacher(school, filters),
            "attendance_accuracy": get_attendance_accuracy(school, filters),
            "performance_per_teacher": get_performance_per_teacher(school, filters),
            "response_times": get_response_times(school, filters),
        }

        return Response(data)

    @action(detail=False, methods=["get"])
    def students(self, request):
        """Student-specific analytics"""
        school = self.get_school()
        serializer = AnalyticsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        data = {
            "total_students": Student.objects.filter(school=school).count(),
            "attendance": get_student_attendance(school, filters),
            "performance": get_student_performance(school, filters),
            "dropouts": get_student_dropouts(school, filters),
            "document_access": get_document_access(school, filters),
        }

        return Response(data)

    @action(detail=False, methods=["get"])
    def classes(self, request):
        """Class-specific analytics"""
        school = self.get_school()
        serializer = AnalyticsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        data = {
            "class_sizes": get_class_sizes(school),
            "average_grades": get_class_average_grades(school, filters),
            "top_classes": get_top_classes(school, filters),
            "attendance_rates": get_class_attendance_rates(school, filters),
            "teacher_ratios": get_teacher_ratios(school),
        }

        return Response(data)

    @action(detail=False, methods=["get"])
    def documents(self, request):
        """Document-specific analytics"""
        school = self.get_school()
        serializer = AnalyticsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        data = {
            "total_documents": Document.objects.filter(school=school).count(),
            "download_frequency": get_document_download_frequency(school, filters),
            "types_distribution": get_document_types_distribution(school),
            "access_by_role": get_document_access_by_role(school, filters),
            "uploads_by_user": get_uploads_by_user(school, filters),
        }

        return Response(data)

    @action(detail=False, methods=["get"])
    def reports(self, request):
        """Report-specific analytics"""
        school = self.get_school()
        serializer = AnalyticsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        data = {
            "reports_generated": get_reports_generated(school, filters),
            "most_accessed": get_most_accessed_reports(school, filters),
            "missing_reports": get_missing_reports(school, filters),
            "top_students": get_top_students_from_reports(school, filters),
            "parent_views": get_parent_report_views(school, filters),
        }

        return Response(data)

    @action(detail=False, methods=["get"])
    def parents(self, request):
        """Parent-specific analytics"""
        school = self.get_school()
        serializer = AnalyticsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        data = {
            "most_engaged": get_most_engaged_parents(school, filters),
            "students_per_parent": get_students_per_parent(school),
            "feedback": get_parent_feedback(school, filters),
            "login_trends": get_parent_login_trends(school, filters),
            "report_views": get_parent_report_views(school, filters),
        }

        return Response(data)

    @action(detail=False, methods=["get"])
    def notifications(self, request):
        """Notification and communication analytics"""
        school = self.get_school()
        serializer = AnalyticsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        data = {
            "open_rates": get_notification_open_rates(school, filters),
            "message_types": get_message_types(school, filters),
            "click_through": get_click_through_rates(school, filters),
            "unread": get_unread_notifications(school),
            "response_times": get_response_times(school, filters),
        }

        return Response(data)

    @action(detail=False, methods=["get"])
    def school_wide(self, request):
        """General school-wide KPIs"""
        school = self.get_school()
        serializer = AnalyticsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        data = {
            "active_users": get_active_users(school, filters),
            "engagement": get_engagement_rates(school, filters),
            "report_generation": get_report_generation_stats(school, filters),
            "teacher_ratios": get_teacher_ratios(school),
            "growth": get_school_growth(school, filters),
        }

        return Response(data)


class AnalyticsDashboardViewSet(viewsets.ModelViewSet):
    queryset = AnalyticsDashboard.objects.all()
    serializer_class = AnalyticsDashboardSerializer
    permission_classes = [IsAuthenticated, IsAdministrator]

    def get_queryset(self):
        return (
            super().get_queryset().filter(school=self.request.user.administered_school)
        )

    def perform_create(self, serializer):
        serializer.save(
            school=self.request.user.administered_school, created_by=self.request.user
        )


class AnalyticsAlertViewSet(viewsets.ModelViewSet):
    queryset = AnalyticsAlert.objects.all()
    serializer_class = AnalyticsAlertSerializer
    permission_classes = [IsAuthenticated, IsAdministrator]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["alert_type", "is_read", "school"]

    def get_queryset(self):
        return (
            super().get_queryset().filter(school=self.request.user.administered_school)
        )

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        alert = self.get_object()
        previous_status = alert.is_read

        # Perform the update
        alert.is_read = True
        alert.save()

        # Log the action
        log_action(
            user=request.user,
            action=f"Marked alert as read: {alert.title}",
            category=ActionCategory.UPDATE,
            obj=alert,
            metadata={"previous_status": previous_status},
        )

        return Response({"status": "marked as read"})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        # Get the filtered queryset - only unread alerts
        queryset = self.filter_queryset(self.get_queryset()).filter(is_read=False)

        # Get counts and sample IDs for logging
        alert_count = queryset.count()
        sample_ids = list(queryset.values_list("id", flat=True)[:5])

        # Perform the bulk update
        updated_count = queryset.update(is_read=True)

        # Log the bulk action
        log_action(
            user=request.user,
            action="Marked all alerts as read",
            category=ActionCategory.UPDATE,
            metadata={
                "total_alerts": alert_count,
                "updated_count": updated_count,
                "sample_alert_ids": sample_ids,
                "filter_criteria": {
                    "alert_type": request.query_params.get("alert_type"),
                    "is_read": request.query_params.get("is_read"),
                    "school": str(request.user.administered_school.id),
                },
            },
        )

        return Response({"status": "all alerts marked as read", "count": updated_count})
