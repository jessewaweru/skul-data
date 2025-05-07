from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.reports.models.report import (
    ReportTemplate,
    ReportSchedule,
    ReportAccessLog,
    ReportNotification,
    AcademicReportConfig,
    TermReportRequest,
    GeneratedReportAccess,  # Added import for GeneratedReportAccess
)
from skul_data.reports.serializers.report import (
    ReportTemplateSerializer,
    ReportScheduleSerializer,
    ReportAccessLogSerializer,
    ReportNotificationSerializer,
)
from skul_data.users.permissions.permission import IsAdministrator, IsTeacher
from django.db import models
from skul_data.reports.models.report import GeneratedReport
from skul_data.reports.serializers.report import (
    GeneratedReportSerializer,
    AcademicReportConfigSerializer,
    TermReportRequestSerializer,
    GeneratedReportAccessSerializer,
)
from skul_data.users.models.base_user import User


class ReportTemplateViewSet(viewsets.ModelViewSet):
    queryset = ReportTemplate.objects.all()
    serializer_class = ReportTemplateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["template_type", "is_system", "school"]

    def get_permissions(self):
        if self.action in ["create", "update", "destroy"]:
            return [IsAdministrator()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return self.queryset

        # For school admins/teachers, show system templates + their school's templates
        school = getattr(user, "school", None)
        if school:
            return self.queryset.filter(
                models.Q(is_system=True) | models.Q(school=school)
            )
        return self.queryset.filter(is_system=True)

    def perform_create(self, serializer):
        user = self.request.user
        # Check if user is a real project-level school admin
        is_system = serializer.validated_data.get("is_system", False)
        if is_system and not user.user_type == User.SCHOOL_ADMIN:
            raise serializers.ValidationError(
                "Only project-level school admins can create system templates."
            )
        # Automatically assign school if it's a school admin
        school = getattr(user, "school", None)
        serializer.save(
            created_by=user,
            school=school if not is_system else None,
        )

    def perform_update(self, serializer):
        user = self.request.user
        is_system = serializer.validated_data.get("is_system", None)

        if is_system and not user.user_type == User.SCHOOL_ADMIN:
            raise serializers.ValidationError(
                "You cannot convert a school template to a system template."
            )

        serializer.save()


class GeneratedReportViewSet(viewsets.ModelViewSet):
    queryset = GeneratedReport.objects.all()
    serializer_class = GeneratedReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "report_type",
        "status",
        "school",
        "generated_by",
        "related_class",
    ]

    def get_permissions(self):
        if self.action in ["create", "update", "destroy", "approve"]:
            return [IsAdministrator()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return self.queryset
        school = getattr(user, "school", None)
        if not school:
            return GeneratedReport.objects.none()

        # Base queryset filtered by school
        queryset = self.queryset.filter(school=school)
        # For teachers, only show reports they generated or are related to their classes/students
        if user.user_type == "teacher":
            teacher = user.teacher_profile
            return queryset.filter(
                models.Q(generated_by=user)
                | models.Q(related_class__teacher_assigned=teacher)
                | models.Q(related_students__in=teacher.assigned_class.students.all())
            ).distinct()

        return queryset

    @action(detail=True, methods=["post"])
    # Custom endpoint to be used for approving reports
    def approve(self, request, pk=None):
        report = self.get_object()
        if not report.requires_approval:
            return Response(
                {"detail": "This report does not require approval"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report.approved_by = request.user
        report.approved_at = timezone.now()
        report.status = "PUBLISHED"
        report.save()

        # Send notifications
        self._send_approval_notifications(report)

        return Response({"status": "approved"})

    def _send_approval_notifications(self, report):
        # Implementation for sending notifications would go here
        pass


class ReportScheduleViewSet(viewsets.ModelViewSet):
    queryset = ReportSchedule.objects.all()
    serializer_class = ReportScheduleSerializer
    permission_classes = [IsAdministrator]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["report_template", "frequency", "is_active", "school"]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return self.queryset

        school = getattr(user, "school", None)
        if school:
            return self.queryset.filter(school=school)

        return ReportSchedule.objects.none()


class ReportAccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReportAccessLog.objects.all()
    serializer_class = ReportAccessLogSerializer
    permission_classes = [IsAdministrator]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["report", "accessed_by", "action"]


class GeneratedReportAccessViewSet(viewsets.ModelViewSet):
    queryset = GeneratedReportAccess.objects.all()
    serializer_class = GeneratedReportAccessSerializer
    permission_classes = [IsAdministrator]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["report", "user", "expires_at"]


class ReportNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReportNotification.objects.all()
    serializer_class = ReportNotificationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["report", "sent_to", "method"]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return self.queryset

        return self.queryset.filter(models.Q(sent_to=user) | models.Q(email=user.email))


class AcademicReportConfigViewSet(viewsets.ModelViewSet):
    queryset = AcademicReportConfig.objects.all()
    serializer_class = AcademicReportConfigSerializer
    permission_classes = [IsAdministrator]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return self.queryset

        school = getattr(user, "school", None)
        if school:
            return self.queryset.filter(school=school)

        return AcademicReportConfig.objects.none()


class TermReportRequestViewSet(viewsets.ModelViewSet):
    queryset = TermReportRequest.objects.all()
    serializer_class = TermReportRequestSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "parent", "term", "school_year", "status"]

    def get_permissions(self):
        if self.action in ["create"]:
            return [permissions.IsAuthenticated()]
        return [IsAdministrator()]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return self.queryset

        # Parents can only see their own requests
        if user.user_type == "parent":
            return self.queryset.filter(parent=user)

        school = getattr(user, "school", None)
        if school:
            return self.queryset.filter(student__school=school)

        return TermReportRequest.objects.none()

    def perform_create(self, serializer):
        parent = self.request.user
        if parent.user_type != "parent":
            raise PermissionDenied("Only parents can request student reports")

        student = serializer.validated_data["student"]
        if not student.guardians.filter(id=parent.id).exists():
            raise PermissionDenied("You can only request reports for your own children")

        serializer.save(parent=parent, status="PENDING")
        # Trigger async report generation
        self._generate_report_async(serializer.instance)

    def _generate_report_async(self, request_instance):
        # Calling the Celery task for this request
        from skul_data.reports.utils.tasks import generate_student_term_report_task

        generate_student_term_report_task.delay(request_instance.id)


class AcademicReportViewSet(viewsets.ViewSet):
    permission_classes = [IsAdministrator | IsTeacher]

    @action(detail=False, methods=["post"])
    def generate_term_reports(self, request):
        """Generate reports for all students in a class for a term"""
        class_id = request.data.get("class_id")
        term = request.data.get("term")
        school_year = request.data.get("school_year")

        if not all([class_id, term, school_year]):
            return Response(
                {"error": "class_id, term and school_year are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify the requesting teacher has access to this class
        if request.user.user_type == "teacher":
            teacher = request.user.teacher_profile
            if not teacher.assigned_class or teacher.assigned_class.id != class_id:
                raise PermissionDenied(
                    "You can only generate reports for your assigned class"
                )

        # In a real implementation, this would call a Celery task
        from skul_data.reports.utils.report_generator import generate_class_term_reports

        task_id = generate_class_term_reports.delay(
            class_id=class_id,
            term=term,
            school_year=school_year,
            generated_by_id=request.user.id,
        )

        return Response({"task_id": str(task_id)}, status=status.HTTP_202_ACCEPTED)
