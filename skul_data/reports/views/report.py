from django.utils import timezone
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.reports.models.report import (
    ReportTemplate,
    GeneratedReport,
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
from skul_data.users.permissions.permission import (
    IsAdministrator,
    IsParent,
    IsSchoolAdmin,
)
from django.db import models
from skul_data.reports.serializers.report import (
    GeneratedReportSerializer,
    AcademicReportConfigSerializer,
    TermReportRequestSerializer,
    GeneratedReportAccessSerializer,
)
from skul_data.users.models.base_user import User
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Student, Subject
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.users.models.base_user import User
from decimal import Decimal
import csv
import io


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

    def perform_create(self, serializer):
        # Add the school and generated_by automatically
        user = self.request.user
        school = getattr(user, "school", None)
        if not school:
            raise serializers.ValidationError("User must be associated with a school")
        serializer.save(school=school, generated_by=user)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        report = self.get_object()

        if not report.requires_approval:
            return Response(
                {"detail": "This report does not require approval"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Store previous status for logging
        previous_status = report.status

        # Update report
        report.approved_by = request.user
        report.approved_at = timezone.now()
        report.status = "PUBLISHED"
        report.save()

        # Log action AFTER successful approval
        log_action(
            user=request.user,
            action=f"Approved report {report.title}",
            category=ActionCategory.UPDATE,
            obj=report,
            metadata={"previous_status": previous_status, "new_status": "PUBLISHED"},
        )

        # Send notifications
        self._send_approval_notifications(report)

        return Response({"status": "approved"})

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Download a generated report file"""
        report = self.get_object()

        # Log the download
        ReportGenerator.log_report_access(
            report=report, user=request.user, action="DOWNLOADED", request=request
        )

        try:
            if not report.file:
                return Response(
                    {"error": "Report file not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Open the file
            file_path = report.file.path
            if not os.path.exists(file_path):
                return Response(
                    {"error": "Report file does not exist"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Determine content type
            content_type = {
                "PDF": "application/pdf",
                "EXCEL": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "CSV": "text/csv",
                "HTML": "text/html",
            }.get(report.file_format, "application/octet-stream")

            # Generate filename
            filename = f"{report.title}.{report.file_format.lower()}"

            # Return file response
            response = FileResponse(open(file_path, "rb"), content_type=content_type)
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            logger.error(f"Error downloading report {report.id}: {str(e)}")
            return Response(
                {"error": "Failed to download report"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def view(self, request, pk=None):
        """View/preview a report in browser"""
        report = self.get_object()

        # Log the view
        ReportGenerator.log_report_access(
            report=report, user=request.user, action="VIEWED", request=request
        )

        try:
            if not report.file:
                return Response(
                    {"error": "Report file not found"}, status=status.HTTP_404_NOT_FOUND
                )

            file_path = report.file.path
            if not os.path.exists(file_path):
                return Response(
                    {"error": "Report file does not exist"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Determine content type
            content_type = {
                "PDF": "application/pdf",
                "HTML": "text/html",
            }.get(report.file_format, "application/octet-stream")

            # Return inline response for viewing
            response = FileResponse(open(file_path, "rb"), content_type=content_type)
            response["Content-Disposition"] = "inline"
            return response

        except Exception as e:
            logger.error(f"Error viewing report {report.id}: {str(e)}")
            return Response(
                {"error": "Failed to view report"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _send_approval_notifications(self, report):
        # Implementation for sending notifications would go here
        pass


class ReportScheduleViewSet(viewsets.ModelViewSet):
    queryset = ReportSchedule.objects.all()
    serializer_class = ReportScheduleSerializer
    # permission_classes = [IsAdministrator]
    permission_classes = [IsSchoolAdmin | IsAdministrator]
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
        if self.action == "create":
            # Allow parents to create requests
            return [IsParent()]
        elif self.action == "list":
            # Allow parents, admins, and teachers to list (with filtering in get_queryset)
            return [permissions.IsAuthenticated()]
        # For other actions like update/delete, require admin
        return [IsAdministrator()]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return self.queryset

        # Parents can only see their own requests
        if user.user_type == User.PARENT:
            return self.queryset.filter(parent=user)

        # Teachers can see requests for their students
        if user.user_type == User.TEACHER:
            teacher = user.teacher_profile
            return self.queryset.filter(student__school_class__teacher_assigned=teacher)

        school = getattr(user, "school", None)
        if school:
            return self.queryset.filter(student__school=school)

        return TermReportRequest.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.user_type != User.PARENT:
            raise PermissionDenied("Only parents can request student reports")

        # Get the parent profile associated with the user
        try:
            parent = user.parent_profile
        except AttributeError:
            raise PermissionDenied("Parent profile not found")

        student = serializer.validated_data["student"]

        # Check both types of relationships
        is_direct_parent = student.parent == parent
        is_guardian = student.guardians.filter(id=parent.id).exists()

        if not (is_direct_parent or is_guardian):
            raise PermissionDenied("You can only request reports for your own children")

        serializer.save(parent=user, status="PENDING")
        # Trigger async report generation
        self._generate_report_async(serializer.instance)

    def _generate_report_async(self, request_instance):
        # Calling the Celery task for this request
        from skul_data.reports.utils.tasks import generate_student_term_report_task

        generate_student_term_report_task.delay(request_instance.id)


class AcademicReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action == "generate_term_reports":
            # Use both permissions
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

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

        if request.user.user_type == "teacher":
            teacher = request.user.teacher_profile
            # Check both M2M and class_teacher relationships
            if not (
                teacher.assigned_classes.filter(id=class_id).exists()
                or SchoolClass.objects.filter(
                    id=class_id, class_teacher=teacher
                ).exists()
            ):
                raise PermissionDenied(
                    "You can only generate reports for your assigned class"
                )

        # In a real implementation, this would call a Celery task
        from skul_data.reports.utils.tasks import generate_class_term_reports_task

        task_id = generate_class_term_reports_task.delay(
            class_id=class_id,
            term=term,
            school_year=school_year,
            generated_by_id=request.user.id,
        )

        return Response({"task_id": str(task_id)}, status=status.HTTP_202_ACCEPTED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_performance_template(request):
    """
    Generate a CSV template for teachers to fill in student performance.
    Teachers can only generate templates for their assigned classes.
    """
    class_id = request.data.get("class_id")
    subject_code = request.data.get("subject_code")
    term = request.data.get("term", "Term 1")
    school_year = request.data.get("school_year", "2025")

    if not class_id or not subject_code:
        return Response(
            {"error": "class_id and subject_code are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        school_class = SchoolClass.objects.get(id=class_id)

        # Permission check: Teachers can only generate for their classes
        user = request.user
        if user.user_type == User.TEACHER:
            teacher = user.teacher_profile
            if school_class.class_teacher != teacher:
                return Response(
                    {
                        "error": "You can only generate templates for your assigned classes"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Get active students
        students = school_class.students.filter(is_active=True).order_by(
            "last_name", "first_name"
        )

        if students.count() == 0:
            return Response(
                {"error": f"No active students found in {school_class.name}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify subject exists
        try:
            subject = Subject.objects.get(code=subject_code, school=school_class.school)
        except Subject.DoesNotExist:
            return Response(
                {"error": f"Subject with code {subject_code} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Generate CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow(
            [
                "admission_number",
                "student_name",
                "subject_code",
                "entry_score",
                "mid_score",
                "end_score",
                "comments",
            ]
        )

        # Instructions row
        writer.writerow(
            [
                "(DO NOT EDIT)",
                "(DO NOT EDIT)",
                subject_code,
                "(0-15)",
                "(0-15)",
                "(0-70)",
                "(Optional remarks)",
            ]
        )

        # Student rows
        for student in students:
            writer.writerow(
                [
                    student.admission_number,
                    student.full_name,
                    subject_code,
                    "",  # entry_score - to be filled
                    "",  # mid_score - to be filled
                    "",  # end_score - to be filled
                    "",  # comments - to be filled
                ]
            )

        # Create HTTP response with CSV
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        filename = f"{school_class.name}_{subject.name}_{term}_{school_year}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except SchoolClass.DoesNotExist:
        return Response({"error": "Class not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_performance(request):
    """
    Upload student performance data from CSV file.
    Creates or updates AcademicRecord entries.
    """
    if "file" not in request.FILES:
        return Response(
            {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
        )

    csv_file = request.FILES["file"]
    class_id = request.data.get("class_id")
    subject_code = request.data.get("subject_code")
    term = request.data.get("term", "Term 1")
    school_year = request.data.get("school_year", "2025")

    if not all([class_id, subject_code, term, school_year]):
        return Response(
            {"error": "class_id, subject_code, term, and school_year are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = request.user

    try:
        # Get teacher profile
        if user.user_type == User.TEACHER:
            teacher = user.teacher_profile
        else:
            # For admins, use the class teacher
            school_class = SchoolClass.objects.get(id=class_id)
            teacher = school_class.class_teacher
            if not teacher:
                return Response(
                    {"error": "No class teacher assigned to this class"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Permission check for teachers
        if user.user_type == User.TEACHER:
            school_class = SchoolClass.objects.get(id=class_id)
            if school_class.class_teacher != teacher:
                return Response(
                    {
                        "error": "You can only upload performance for your assigned classes"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Get subject
        subject = Subject.objects.get(code=subject_code, school=teacher.school)

        # Process CSV file
        decoded_file = csv_file.read().decode("utf-8")
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        created = 0
        updated = 0
        errors = []

        for row_num, row in enumerate(reader, start=1):
            # Skip instruction row
            if row["admission_number"] == "(DO NOT EDIT)":
                continue

            try:
                # Validate required fields
                if not row.get("admission_number"):
                    errors.append({"row": row_num, "error": "Missing admission number"})
                    continue

                # Get student
                student = Student.objects.get(
                    admission_number=row["admission_number"], school=teacher.school
                )

                # Validate and calculate scores
                try:
                    entry = int(row.get("entry_score") or 0)
                    mid = int(row.get("mid_score") or 0)
                    end = int(row.get("end_score") or 0)

                    # Validate score ranges
                    if not (0 <= entry <= 15):
                        raise ValueError("Entry score must be 0-15")
                    if not (0 <= mid <= 15):
                        raise ValueError("Mid score must be 0-15")
                    if not (0 <= end <= 70):
                        raise ValueError("End score must be 0-70")

                    total_score = entry + mid + end

                except ValueError as e:
                    errors.append(
                        {
                            "row": row_num,
                            "student": row.get("student_name", "Unknown"),
                            "error": f"Invalid score: {str(e)}",
                        }
                    )
                    continue

                # Create or update academic record
                record, is_new = AcademicRecord.objects.update_or_create(
                    student=student,
                    subject=subject,
                    term=term,
                    school_year=school_year,
                    defaults={
                        "teacher": teacher,
                        "score": Decimal(str(total_score)),
                        "subject_comments": row.get("comments", ""),
                        "is_published": False,  # Not published until reviewed
                    },
                )

                if is_new:
                    created += 1
                else:
                    updated += 1

            except Student.DoesNotExist:
                errors.append(
                    {
                        "row": row_num,
                        "error": f"Student with admission number {row.get('admission_number')} not found",
                    }
                )
            except Exception as e:
                errors.append(
                    {
                        "row": row_num,
                        "student": row.get("student_name", "Unknown"),
                        "error": str(e),
                    }
                )

        # Return summary
        return Response(
            {
                "created": created,
                "updated": updated,
                "errors": errors,
                "total_processed": created + updated,
                "message": f"Successfully processed {created + updated} records",
            },
            status=status.HTTP_200_OK,
        )

    except SchoolClass.DoesNotExist:
        return Response({"error": "Class not found"}, status=status.HTTP_404_NOT_FOUND)
    except Subject.DoesNotExist:
        return Response(
            {"error": f"Subject with code {subject_code} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Upload failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
