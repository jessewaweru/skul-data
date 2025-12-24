from django.db import models
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets
from django.conf import settings
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.users.permissions.permission import IsAdministrator, IsSchoolAdmin
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


class AnalyticsSchoolPermission:
    """
    Custom permission that allows both School Admins and Administrators
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Allow School Admins
        if request.user.user_type == User.SCHOOL_ADMIN:
            return hasattr(request.user, "school_admin_profile")

        # Allow Administrators
        if request.user.user_type == User.ADMINISTRATOR:
            return True

        # Allow Teacher Administrators
        if request.user.user_type == User.TEACHER:
            try:
                return request.user.teacher_profile.is_administrator
            except Teacher.DoesNotExist:
                return False

        return False


class AnalyticsViewSet(viewsets.ViewSet):
    # Updated permission classes to include School Admins
    permission_classes = [IsAuthenticated]  # We'll handle the logic in get_school()

    def get_school(self):
        """Get the school for the current user with proper permission checking"""
        user = self.request.user

        # Check permissions first
        if user.user_type == User.SCHOOL_ADMIN and hasattr(
            user, "school_admin_profile"
        ):
            return user.school_admin_profile.school
        elif user.user_type == User.ADMINISTRATOR and hasattr(
            user, "administered_school"
        ):
            return user.administered_school
        elif user.user_type == User.TEACHER and hasattr(user, "teacher_profile"):
            if user.teacher_profile.is_administrator:
                return user.teacher_profile.school

        # If no valid permission/school found, raise permission denied
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("You do not have permission to access analytics data.")

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """Default overview with top 5 metrics"""
        school = self.get_school()

        # Check for cached data first
        cached = CachedAnalytics.objects.filter(
            school=school, analytics_type="overview", valid_until__gte=timezone.now()
        ).first()

        if cached:
            # Transform the cached data to match frontend expectations
            transformed_data = self._transform_overview_data(cached.data)
            return Response(transformed_data)

        # Get fresh data if not cached
        overview_cache = CachedAnalytics.objects.filter(
            school=school, analytics_type="overview"
        ).first()

        if overview_cache:
            # Transform and return the data
            transformed_data = self._transform_overview_data(overview_cache.data)
            return Response(transformed_data)

        # Return empty structure if no data
        return Response(
            {
                "most_active_teacher": {"name": "N/A", "login_count": 0},
                "student_attendance_rate": 0,
                "most_downloaded_document": {"title": "N/A", "download_count": 0},
                "top_performing_class": {"class_name": "N/A", "average_score": 0},
                "reports_generated": 0,
                "teacher_activity": [],
                "attendance_trend": [],
                "document_usage": [],
                "class_performance": [],
            }
        )

    def _transform_overview_data(self, data):
        """Transform the cached data to match frontend chart expectations"""
        transformed = data.copy()

        # Transform teacher_activity data for charts
        if "teacher_activity" in data and isinstance(data["teacher_activity"], list):
            transformed["teacher_activity"] = [
                {
                    "name": teacher.get("user__first_name", "")
                    + " "
                    + teacher.get("user__last_name", ""),
                    "logins": teacher.get("login_count", 0),
                    "reports": teacher.get("reports_count", 0),
                }
                for teacher in data["teacher_activity"][:5]  # Top 5 teachers
            ]
        else:
            transformed["teacher_activity"] = []

        # Transform attendance_trend data for charts
        if "attendance_trend" in data and isinstance(data["attendance_trend"], list):
            transformed["attendance_trend"] = [
                {"date": item.get("date", ""), "attendance": item.get("rate", 0)}
                for item in data["attendance_trend"]
            ]
        else:
            # Create sample attendance trend data
            from datetime import datetime, timedelta

            base_date = datetime.now() - timedelta(days=7)
            transformed["attendance_trend"] = [
                {
                    "date": (base_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                    "attendance": 80 + (i * 2),  # Sample trend
                }
                for i in range(7)
            ]

        # Transform document_usage data for charts
        if "document_usage" in data and isinstance(data["document_usage"], list):
            transformed["document_usage"] = [
                {"name": doc.get("type", "Unknown"), "value": doc.get("count", 0)}
                for doc in data["document_usage"]
            ]
        else:
            transformed["document_usage"] = []

        # Transform class_performance data for charts
        if "class_performance" in data and isinstance(data["class_performance"], list):
            transformed["class_performance"] = [
                {
                    "name": cls.get("class_name", "Unknown"),
                    "average": cls.get("average_score", 0),
                    "top": cls.get("top_score", 0),
                }
                for cls in data["class_performance"]
            ]
        else:
            transformed["class_performance"] = []

        return transformed

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

    # @action(detail=False, methods=["get"])
    # def documents(self, request):
    #     """Document-specific analytics with improved error handling"""
    #     try:
    #         school = self.get_school()
    #         if not school:
    #             return Response(
    #                 {"error": "School not found"}, status=status.HTTP_400_BAD_REQUEST
    #             )

    #         # Create serializer instance and validate
    #         serializer = AnalyticsFilterSerializer(data=request.query_params)
    #         if not serializer.is_valid():
    #             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    #         filters = serializer.validated_data

    #         # Log the request for debugging
    #         print(f"Documents analytics request for school: {school.name}")
    #         print(f"Filters: {filters}")

    #         # Check for cached data first
    #         cached = CachedAnalytics.objects.filter(
    #             school=school,
    #             analytics_type="documents",
    #             valid_until__gte=timezone.now(),
    #         ).first()

    #         if cached:
    #             print("Returning cached document analytics")
    #             return Response(cached.data)

    #         # Generate fresh data
    #         try:
    #             data = {
    #                 "total_documents": Document.objects.filter(school=school).count(),
    #                 "download_frequency": get_document_download_frequency(
    #                     school, filters
    #                 ),
    #                 "types_distribution": get_document_types_distribution(school),
    #                 "access_by_role": get_document_access_by_role(school, filters),
    #                 "uploads_by_user": get_uploads_by_user(school, filters),
    #             }

    #             print(f"Generated document analytics data: {data}")

    #             # Cache the data for 1 hour
    #             CachedAnalytics.objects.create(
    #                 school=school,
    #                 analytics_type="documents",
    #                 data=data,
    #                 valid_until=timezone.now() + timedelta(hours=1),
    #             )

    #             return Response(data)

    #         except Exception as e:
    #             print(f"Error generating document analytics: {str(e)}")
    #             return Response(
    #                 {
    #                     "error": "Failed to generate analytics data",
    #                     "details": str(e) if settings.DEBUG else None,
    #                 },
    #                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #             )

    #     except Exception as e:
    #         print(f"Unexpected error in documents analytics: {str(e)}")
    #         return Response(
    #             {
    #                 "error": "An unexpected error occurred",
    #                 "details": str(e) if settings.DEBUG else None,
    #             },
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         )

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
    permission_classes = [IsAuthenticated, IsSchoolAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AnalyticsDashboard.objects.none()
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            school = user.school_admin_profile.school
        else:
            school = self.request.user.administered_school
        return super().get_queryset().filter(school=school)

    def perform_create(self, serializer):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            school = user.school_admin_profile.school
        else:
            school = self.request.user.administered_school
        serializer.save(school=school, created_by=self.request.user)


class AnalyticsAlertViewSet(viewsets.ModelViewSet):
    queryset = AnalyticsAlert.objects.all()
    serializer_class = AnalyticsAlertSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["alert_type", "is_read", "school"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AnalyticsAlert.objects.none()

        # Handle both school admin and administrator users
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            school = user.school_admin_profile.school
        else:
            school = self.request.user.administered_school
        return super().get_queryset().filter(school=school)

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
                    "school": str(
                        request.user.school_admin_profile.school.id
                        if request.user.user_type == User.SCHOOL_ADMIN
                        else request.user.administered_school.id
                    ),
                },
            },
        )

        return Response({"status": "all alerts marked as read", "count": updated_count})
