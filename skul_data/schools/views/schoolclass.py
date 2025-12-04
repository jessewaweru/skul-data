from venv import logger
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.db.models import Count, Avg
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.schools.serializers.schoolclass import (
    SchoolClassCreateSerializer,
    SchoolClassPromoteSerializer,
    SchoolClassSerializer,
    ClassTimetableSerializer,
    ClassDocumentSerializer,
    ClassAttendanceSerializer,
    ClassAttendance,
    ClassDocument,
    ClassTimetable,
)
from skul_data.users.permissions.permission import IsTeacher, IsAdministrator
from skul_data.users.models.base_user import User
from django.db import models
from skul_data.users.permissions.permission import HasRolePermission
from skul_data.students.models.student import Student
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.reports.models.academic_record import AcademicRecord
from django.utils import timezone
from datetime import timedelta


class SchoolClassViewSet(viewsets.ModelViewSet):
    queryset = SchoolClass.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "grade_level",
        "stream",
        "level",
        "academic_year",
        "is_active",
        "class_teacher",
        "school",
    ]
    search_fields = ["name", "room_number"]
    permission_classes = [IsAuthenticated, HasRolePermission]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SchoolClassCreateSerializer
        elif self.action == "promote":
            return SchoolClassPromoteSerializer
        return SchoolClassSerializer

    # def get_permissions(self):
    #     if self.action in ["create", "update", "destroy", "promote", "assign_teacher"]:
    #         return [IsAdministrator()]
    #     elif self.action in ["retrieve", "list", "analytics"]:
    #         # Allow both admins and teachers
    #         return [IsAuthenticated(), HasRolePermission()]
    #     return [IsAuthenticated()]

    # Set required permissions for HasRolePermission
    required_permission_get = "view_classes"
    required_permission_post = "manage_classes"
    required_permission_put = "manage_classes"
    required_permission_delete = "manage_classes"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return SchoolClass.objects.none()

        # Optimize queries with select_related and prefetch_related
        queryset = queryset.select_related(
            "school", "stream", "class_teacher__user"
        ).prefetch_related(
            "students__parent__user", "students__guardians__user", "subjects"
        )

        # Get school for admin
        if user.user_type == User.SCHOOL_ADMIN:
            try:
                admin_profile = user.school_admin_profile
                return queryset.filter(school=admin_profile.school)
            except SchoolAdmin.DoesNotExist:
                return SchoolClass.objects.none()

        return SchoolClass.objects.none()

    def perform_create(self, serializer):
        """Override to add logging for class creation"""
        school_class = serializer.save()

        # Log the class creation
        log_action(
            user=self.request.user,
            action="Created class",
            category=ActionCategory.CREATE,
            obj=school_class,
            metadata={
                "class_name": school_class.name,
                "grade_level": school_class.grade_level,
                "school": str(school_class.school),
            },
        )

    @action(detail=True, methods=["post"])
    def promote(self, request, pk=None):
        """Promote class to next academic year"""
        class_instance = self.get_object()
        serializer = SchoolClassPromoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            new_class = class_instance.promote_class(
                serializer.validated_data["new_academic_year"]
            )

            # Log the class promotion
            log_action(
                user=request.user,
                action="Promoted class",
                category=ActionCategory.UPDATE,
                obj=class_instance,
                metadata={
                    "new_academic_year": serializer.validated_data["new_academic_year"],
                    "original_year": class_instance.academic_year,
                    "new_class_id": new_class.id,
                },
            )

            return Response(
                SchoolClassSerializer(new_class).data, status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def assign_teacher(self, request, pk=None):
        class_instance = self.get_object()
        teacher_id = request.data.get("teacher_id")

        if not teacher_id:
            return Response(
                {"error": "teacher_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Update this import to match your actual Teacher model location
            from skul_data.users.models.teacher import (
                Teacher,
            )  # or wherever your Teacher model is

            teacher = Teacher.objects.get(id=teacher_id, school=class_instance.school)
            old_teacher = class_instance.class_teacher
            class_instance.class_teacher = teacher
            class_instance.save()

            # Log the teacher assignment
            log_action(
                user=request.user,
                action="Assigned teacher to class",
                category=ActionCategory.UPDATE,
                obj=class_instance,
                metadata={
                    "fields_changed": ["class_teacher"],
                    "new_teacher": str(teacher),
                    "old_teacher": str(old_teacher) if old_teacher else None,
                },
            )

            return Response(
                SchoolClassSerializer(class_instance).data, status=status.HTTP_200_OK
            )
        except Teacher.DoesNotExist:
            return Response(
                {"error": "Teacher not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["get"], url_path="analytics")
    def analytics(self, request, pk=None):
        """Detailed analytics for a specific class"""
        try:
            class_instance = self.get_object()

            # Debug logging
            logger.info(
                f"Generating analytics for class: {class_instance.name} (ID: {class_instance.id})"
            )

            # Get basic class info
            class_info = {
                "class_id": class_instance.id,
                "class_name": class_instance.name,
                "grade_level": class_instance.grade_level,
                "stream": class_instance.stream.name if class_instance.stream else None,
                "academic_year": class_instance.academic_year,
            }

            # Get students in the class
            class_students = class_instance.students.all()
            total_students = class_students.count()

            logger.info(f"Total students in class: {total_students}")

            # Initialize default values
            avg_performance = 0
            attendance_rate = 0
            performance_distribution = {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0, "f": 0}
            subject_performance = []
            attendance_by_month = []
            top_student = None

            # Get attendance data (last 6 months) - Check if attendance records exist
            try:
                six_months_ago = timezone.now() - timedelta(days=180)
                attendance_records = class_instance.attendances.filter(
                    date__gte=six_months_ago
                ).order_by("-date")

                # Process attendance records
                for record in attendance_records[:6]:  # Limit to 6 records
                    try:
                        present_count = (
                            record.present_students.count()
                            if hasattr(record, "present_students")
                            else 0
                        )
                        total_count = (
                            record.total_students
                            if hasattr(record, "total_students")
                            else total_students
                        )
                        rate = (
                            (present_count / total_count * 100)
                            if total_count > 0
                            else 0
                        )

                        attendance_by_month.append(
                            {
                                "month": record.date.strftime("%b %Y"),
                                "attendance_rate": round(rate, 1),
                                "present": present_count,
                                "total": total_count,
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Error processing attendance record: {str(e)}")

                # Get latest attendance rate
                latest_attendance = attendance_records.first()
                if latest_attendance:
                    try:
                        present_count = (
                            latest_attendance.present_students.count()
                            if hasattr(latest_attendance, "present_students")
                            else 0
                        )
                        total_count = (
                            latest_attendance.total_students
                            if hasattr(latest_attendance, "total_students")
                            else total_students
                        )
                        attendance_rate = (
                            (present_count / total_count * 100)
                            if total_count > 0
                            else 0
                        )
                    except:
                        attendance_rate = 0
            except Exception as e:
                logger.warning(f"Error processing attendance data: {str(e)}")

            # Get performance data - Check if academic records exist
            try:
                academic_records = AcademicRecord.objects.filter(
                    student__in=class_students
                )

                logger.info(f"Found {academic_records.count()} academic records")

                if academic_records.exists():
                    # Performance distribution
                    total_records = academic_records.count()
                    performance_distribution = {
                        "a": academic_records.filter(score__gte=80).count(),
                        "b": academic_records.filter(
                            score__gte=70, score__lt=80
                        ).count(),
                        "c": academic_records.filter(
                            score__gte=60, score__lt=70
                        ).count(),
                        "d": academic_records.filter(
                            score__gte=50, score__lt=60
                        ).count(),
                        "e": academic_records.filter(
                            score__gte=40, score__lt=50
                        ).count(),
                        "f": academic_records.filter(score__lt=40).count(),
                    }

                    # Calculate average performance
                    avg_performance = (
                        academic_records.aggregate(avg_score=Avg("score"))["avg_score"]
                        or 0
                    )

                    # Subject performance
                    subjects = class_instance.subjects.all()
                    for subject in subjects:
                        try:
                            subject_records = academic_records.filter(subject=subject)
                            if subject_records.exists():
                                subject_avg = (
                                    subject_records.aggregate(avg=Avg("score"))["avg"]
                                    or 0
                                )
                                top_student_record = subject_records.order_by(
                                    "-score"
                                ).first()

                                subject_performance.append(
                                    {
                                        "name": subject.name,
                                        "average_score": round(subject_avg, 2),
                                        "top_student": {
                                            "name": (
                                                top_student_record.student.user.get_full_name()
                                                if top_student_record
                                                and hasattr(
                                                    top_student_record.student, "user"
                                                )
                                                else "N/A"
                                            ),
                                            "score": (
                                                round(top_student_record.score, 2)
                                                if top_student_record
                                                else 0
                                            ),
                                        },
                                    }
                                )
                        except Exception as e:
                            logger.warning(
                                f"Error processing subject {subject.name}: {str(e)}"
                            )

                    # Top student overall
                    try:
                        top_student_data = (
                            class_students.annotate(
                                avg_score=Avg("academic_records__score")
                            )
                            .exclude(avg_score__isnull=True)
                            .order_by("-avg_score")
                            .first()
                        )

                        if top_student_data and top_student_data.avg_score:
                            top_student = {
                                "name": (
                                    top_student_data.user.get_full_name()
                                    if hasattr(top_student_data, "user")
                                    else "N/A"
                                ),
                                "score": round(top_student_data.avg_score, 2),
                            }
                    except Exception as e:
                        logger.warning(f"Error finding top student: {str(e)}")

            except Exception as e:
                logger.warning(f"Error processing academic records: {str(e)}")

            # Build response data
            response_data = {
                **class_info,
                "average_performance": round(avg_performance, 2),
                "attendance_rate": round(attendance_rate, 2),
                "performance_distribution": performance_distribution,
                "subject_performance": subject_performance,
                "attendance_by_month": attendance_by_month,
                "top_student": top_student,
                "performance_trend": "up",  # Placeholder - implement actual trend calculation
                "performance_change": 5.2,  # Placeholder
                "attendance_trend": "up",  # Placeholder
                "attendance_change": 3.1,  # Placeholder
                "total_students": total_students,
            }

            logger.info(
                f"Successfully generated analytics for class {class_instance.name}"
            )
            return Response(response_data)

        except Exception as e:
            logger.error(f"Error generating class analytics: {str(e)}")
            logger.exception("Full traceback:")  # This will log the full stack trace
            return Response(
                {"error": "Failed to generate analytics data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def attendance_stats(self, request, pk=None):
        """Get attendance statistics for a specific class"""
        class_instance = self.get_object()

        # Log the stats view
        log_action(
            user=request.user,
            action=f"Viewed attendance stats for {class_instance.name}",
            category=ActionCategory.VIEW,
            obj=class_instance,
            metadata={"class_id": class_instance.id},
        )

        # Get all attendance records for this class
        attendance_records = ClassAttendance.objects.filter(
            school_class=class_instance
        ).order_by("-date")

        if not attendance_records.exists():
            return Response(
                {
                    "current_attendance_rate": 0,
                    "total_students": class_instance.students.count(),
                    "best_day": None,
                    "worst_day": None,
                    "total_records": 0,
                }
            )

        # Calculate statistics
        total_students = class_instance.students.count()
        attendance_rates = []

        for record in attendance_records:
            present_count = record.present_students.count()
            rate = (present_count / total_students * 100) if total_students > 0 else 0
            attendance_rates.append(
                {
                    "date": record.date,
                    "rate": rate,
                    "present": present_count,
                    "total": total_students,
                }
            )

        # Current (average) attendance rate
        current_rate = sum(r["rate"] for r in attendance_rates) / len(attendance_rates)

        # Best and worst days
        best_day = (
            max(attendance_rates, key=lambda x: x["rate"]) if attendance_rates else None
        )
        worst_day = (
            min(attendance_rates, key=lambda x: x["rate"]) if attendance_rates else None
        )

        return Response(
            {
                "current_attendance_rate": round(current_rate, 2),
                "total_students": total_students,
                "best_day": (
                    {
                        "date": best_day["date"].strftime("%Y-%m-%d"),
                        "rate": round(best_day["rate"], 1),
                    }
                    if best_day
                    else None
                ),
                "worst_day": (
                    {
                        "date": worst_day["date"].strftime("%Y-%m-%d"),
                        "rate": round(worst_day["rate"], 1),
                    }
                    if worst_day
                    else None
                ),
                "total_records": len(attendance_rates),
            }
        )


class ClassTimetableViewSet(viewsets.ModelViewSet):
    queryset = ClassTimetable.objects.all()
    serializer_class = ClassTimetableSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["school_class", "is_active"]
    permission_classes = [IsAuthenticated, HasRolePermission]

    # Set specific permissions
    required_permission_get = "view_class_timetables"
    required_permission_post = "manage_class_timetables"
    required_permission_put = "manage_class_timetables"
    required_permission_delete = "manage_class_timetables"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Get the user's school
        school = None
        if user.user_type == User.SCHOOL_ADMIN:
            try:
                school = user.schooladmin.school
            except AttributeError:
                return ClassTimetable.objects.none()
        elif hasattr(user, "school"):
            school = user.school

        if not school:
            return ClassTimetable.objects.none()

        # Filter by school
        queryset = queryset.filter(school_class__school=school)

        # Teachers can only see their assigned classes' timetables
        if user.user_type == "teacher":
            return queryset.filter(school_class__class_teacher=user.teacher_profile)

        return queryset


class ClassDocumentViewSet(viewsets.ModelViewSet):
    queryset = ClassDocument.objects.all()
    serializer_class = ClassDocumentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["school_class", "document_type", "created_by"]
    search_fields = ["title", "description"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        print(f"DEBUG: User type: {user.user_type}")
        print(f"DEBUG: User: {user}")

        # Get the user's school
        school = None
        if user.user_type == User.SCHOOL_ADMIN:
            try:
                # Fix: Use school_admin_profile instead of schooladmin
                school = user.school_admin_profile.school
                print(f"DEBUG: School from admin profile: {school}")
            except AttributeError as e:
                print(f"DEBUG: Error accessing school admin profile: {e}")
                # Fallback: try direct school attribute
                if hasattr(user, "school"):
                    school = user.school
                    print(f"DEBUG: School from direct attribute: {school}")
                else:
                    print("DEBUG: No school found for user")
                    return ClassDocument.objects.none()
        elif hasattr(user, "school"):
            school = user.school
            print(f"DEBUG: School from direct attribute: {school}")

        if not school:
            print("DEBUG: No school found, returning empty queryset")
            return ClassDocument.objects.none()

        # Filter by school
        queryset = queryset.filter(school_class__school=school)
        print(f"DEBUG: Queryset after school filter: {queryset.count()} documents")

        # For debugging: let's see what documents exist for this school
        all_docs_for_school = ClassDocument.objects.filter(school_class__school=school)
        print(
            f"DEBUG: Total documents for school {school}: {all_docs_for_school.count()}"
        )
        for doc in all_docs_for_school:
            print(
                f"  - {doc.title} (Class: {doc.school_class.id} - {doc.school_class.name})"
            )

        # Temporarily remove teacher restriction to test
        # TODO: Re-enable this after confirming documents are visible
        if user.user_type == "teacher":
            teacher_queryset = queryset.filter(
                models.Q(school_class__class_teacher=user.teacher_profile)
                | models.Q(created_by=user)
            )
            print(
                f"DEBUG: Teacher filtered queryset: {teacher_queryset.count()} documents"
            )
            return teacher_queryset

        return queryset

    def perform_create(self, serializer):
        # Check if teacher is assigned to the class
        school_class = serializer.validated_data.get("school_class")
        user = self.request.user

        if (
            user.user_type == "teacher"
            and school_class.class_teacher != user.teacher_profile
        ):
            # If teacher is not assigned to this class, raise permission error
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "You can only create documents for classes you teach"
            )

        serializer.save(created_by=self.request.user)


class ClassAttendanceViewSet(viewsets.ModelViewSet):
    queryset = ClassAttendance.objects.all()
    serializer_class = ClassAttendanceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["school_class", "date", "taken_by"]
    permission_classes = [IsAuthenticated, HasRolePermission]

    required_permission_get = "view_attendance"
    required_permission_post = "manage_attendance"
    required_permission_put = "manage_attendance"
    required_permission_delete = "manage_attendance"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            # Admin sees all attendance for their school
            if hasattr(user, "school_admin_profile"):
                school = user.school_admin_profile.school
                return queryset.filter(school_class__school=school)
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return ClassAttendance.objects.none()

        queryset = queryset.filter(school_class__school=school)

        if user.user_type == User.TEACHER:
            # Teachers see attendance for their classes
            return queryset.filter(
                Q(school_class__class_teacher=user.teacher_profile) | Q(taken_by=user)
            )

        return queryset

    def _notify_parents_about_attendance(self, attendance):
        """
        Send notifications to parents about attendance.
        This method handles Database notifications, WebSocket notifications,
        and Email notifications (when configured).
        """
        from skul_data.notifications.models.notification import Notification
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        import logging

        logger = logging.getLogger(__name__)

        # Get all students in the class
        all_students = attendance.school_class.students.all()
        present_students = set(attendance.present_students.all())

        # Get channel layer for WebSocket notifications
        channel_layer = get_channel_layer()

        # Notify parents of PRESENT students
        for student in present_students:
            parents = []
            if student.parent:
                parents.append(student.parent)
            parents.extend(list(student.guardians.all()))

            for parent in parents:
                try:
                    # 1. Create database notification
                    notification = Notification.objects.create(
                        user=parent.user,
                        notification_type="SYSTEM",
                        title=f"✓ Attendance Confirmed: {student.full_name}",
                        message=(
                            f"{student.full_name} attended {attendance.school_class.name} "
                            f"on {attendance.date.strftime('%B %d, %Y')}.\n\n"
                            f"Class: {attendance.school_class.name}\n"
                            f"Time: {attendance.created_at.strftime('%I:%M %p')}\n"
                            f"Recorded by: {attendance.taken_by.get_full_name() if attendance.taken_by else 'System'}"
                        ),
                        related_model="ClassAttendance",
                        related_id=attendance.id,
                    )

                    # 2. Send WebSocket notification (real-time)
                    if channel_layer:
                        try:
                            async_to_sync(channel_layer.group_send)(
                                f"notifications_{parent.user.id}",
                                {
                                    "type": "notification.message",
                                    "message": {
                                        "id": notification.id,
                                        "type": "SYSTEM",
                                        "title": notification.title,
                                        "message": notification.message,
                                        "student_name": student.full_name,
                                        "class_name": attendance.school_class.name,
                                        "date": attendance.date.isoformat(),
                                        "is_present": True,
                                        "created_at": notification.created_at.isoformat(),
                                    },
                                },
                            )
                        except Exception as e:
                            logger.warning(f"WebSocket notification failed: {str(e)}")

                    # 3. Send Email notification (if configured)
                    self._send_attendance_email(
                        parent, student, attendance, is_present=True
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to notify parent {parent.user.email} about attendance: {str(e)}"
                    )

        # Notify parents of ABSENT students
        absent_students = [s for s in all_students if s not in present_students]

        for student in absent_students:
            # Extract absence reason for this student
            absence_reason = ""
            if attendance.notes:
                for line in attendance.notes.split("\n"):
                    if student.full_name in line:
                        absence_reason = (
                            line.split(":", 1)[1].strip() if ":" in line else ""
                        )
                        break

            parents = []
            if student.parent:
                parents.append(student.parent)
            parents.extend(list(student.guardians.all()))

            for parent in parents:
                try:
                    # 1. Create database notification
                    message = (
                        f"{student.full_name} was absent from {attendance.school_class.name} "
                        f"on {attendance.date.strftime('%B %d, %Y')}.\n\n"
                        f"Class: {attendance.school_class.name}\n"
                        f"Date: {attendance.date.strftime('%B %d, %Y')}\n"
                    )
                    if absence_reason:
                        message += f"Reason: {absence_reason}\n"
                    else:
                        message += "Reason: Not specified\n"

                    message += f"\nIf this is incorrect, please contact {attendance.taken_by.get_full_name() if attendance.taken_by else 'the school'}."

                    notification = Notification.objects.create(
                        user=parent.user,
                        notification_type="EVENT",
                        title=f"⚠ Absence Alert: {student.full_name}",
                        message=message,
                        related_model="ClassAttendance",
                        related_id=attendance.id,
                    )

                    # 2. Send WebSocket notification
                    if channel_layer:
                        try:
                            async_to_sync(channel_layer.group_send)(
                                f"notifications_{parent.user.id}",
                                {
                                    "type": "notification.message",
                                    "message": {
                                        "id": notification.id,
                                        "type": "EVENT",
                                        "title": notification.title,
                                        "message": notification.message,
                                        "student_name": student.full_name,
                                        "class_name": attendance.school_class.name,
                                        "date": attendance.date.isoformat(),
                                        "is_present": False,
                                        "absence_reason": absence_reason,
                                        "created_at": notification.created_at.isoformat(),
                                    },
                                },
                            )
                        except Exception as e:
                            logger.warning(f"WebSocket notification failed: {str(e)}")

                    # 3. Send Email notification
                    self._send_attendance_email(
                        parent,
                        student,
                        attendance,
                        is_present=False,
                        absence_reason=absence_reason,
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to notify parent {parent.user.email} about absence: {str(e)}"
                    )

    def _send_attendance_email(
        self, parent, student, attendance, is_present, absence_reason=None
    ):
        """
        Send email notification to parent.
        This will fail silently if email is not configured.
        """
        try:
            from django.core.mail import EmailMessage
            from django.conf import settings
            import logging

            logger = logging.getLogger(__name__)

            # Check if email is configured
            if not hasattr(settings, "EMAIL_HOST") or not settings.EMAIL_HOST:
                logger.info("Email not configured - skipping email notification")
                return False

            school = attendance.school_class.school

            # Prepare email content
            if is_present:
                subject = f"✓ {student.full_name} - Attendance Confirmed"
                message = (
                    f"Dear {parent.user.first_name},\n\n"
                    f"This is to confirm that {student.full_name} attended {attendance.school_class.name} "
                    f"on {attendance.date.strftime('%B %d, %Y')}.\n\n"
                    f"Class: {attendance.school_class.name}\n"
                    f"Time: {attendance.created_at.strftime('%I:%M %p')}\n"
                    f"Recorded by: {attendance.taken_by.get_full_name() if attendance.taken_by else 'System'}\n\n"
                    f"Best regards,\n{school.name}"
                )
            else:
                subject = f"⚠ {student.full_name} - Absence Alert"
                message = (
                    f"Dear {parent.user.first_name},\n\n"
                    f"{student.full_name} was marked absent from {attendance.school_class.name} "
                    f"on {attendance.date.strftime('%B %d, %Y')}.\n\n"
                    f"Class: {attendance.school_class.name}\n"
                )
                if absence_reason:
                    message += f"Reason: {absence_reason}\n"
                message += (
                    f"\nIf this is incorrect, please contact the school immediately.\n\n"
                    f"Best regards,\n{school.name}"
                )

            # Create and send email
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[parent.user.email],
            )

            email.send(fail_silently=True)
            logger.info(f"Attendance email sent to {parent.user.email}")
            return True

        except Exception as e:
            # Log but don't raise - email is optional
            logger.warning(
                f"Email notification failed (this is OK if email not configured): {str(e)}"
            )
            return False

    def perform_create(self, serializer):
        user = self.request.user
        school_class = serializer.validated_data.get("school_class")

        # Check if teacher can take attendance for this class
        if (
            user.user_type == User.TEACHER
            and school_class.class_teacher != user.teacher_profile
        ):
            raise PermissionDenied(
                "You can only take attendance for your assigned classes"
            )

        # Save attendance
        attendance = serializer.save(taken_by=user)

        # Send notifications to parents (Database + WebSocket + Email if configured)
        self._notify_parents_about_attendance(attendance)

    @action(detail=True, methods=["post"])
    def mark_attendance(self, request, pk=None):
        """Mark attendance for students with optional absence reasons"""
        attendance = self.get_object()
        student_ids = request.data.get("student_ids", [])
        absent_reasons = request.data.get("absent_reasons", {})

        # Check permissions
        if (
            request.user.user_type == User.TEACHER
            and attendance.school_class.class_teacher != request.user.teacher_profile
        ):
            raise PermissionDenied(
                "You can only mark attendance for your assigned classes"
            )

        try:
            # Update attendance
            attendance._current_user = request.user
            attendance.update_attendance(student_ids, user=request.user)

            # Store absence reasons in notes
            if absent_reasons:
                absent_notes = []
                for student_id, reason in absent_reasons.items():
                    try:
                        student = Student.objects.get(id=student_id)
                        absent_notes.append(f"{student.full_name}: {reason}")
                    except Student.DoesNotExist:
                        pass

                if absent_notes:
                    attendance.notes = "\n".join(absent_notes)
                    attendance.save(update_fields=["notes"])

            # Send notifications to parents (Database + WebSocket + Email if configured)
            self._notify_parents_about_attendance(attendance)

            # Log the action
            log_action(
                user=request.user,
                action="Marked attendance",
                category=ActionCategory.UPDATE,
                obj=attendance,
                metadata={
                    "total_present": len(student_ids),
                    "student_ids": student_ids,
                    "absent_reasons": absent_reasons,
                },
            )

            return Response(
                ClassAttendanceSerializer(attendance).data, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def stats_by_class(self, request):
        """Get attendance statistics for a specific class"""
        class_id = request.query_params.get("class_id")

        if not class_id:
            return Response(
                {"error": "class_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            school_class = SchoolClass.objects.get(id=class_id)

            # Check permissions
            if request.user.user_type == User.SCHOOL_ADMIN:
                if (
                    not hasattr(request.user, "school_admin_profile")
                    or request.user.school_admin_profile.school != school_class.school
                ):
                    raise PermissionDenied()
            elif request.user.user_type == User.TEACHER:
                if school_class.class_teacher != request.user.teacher_profile:
                    raise PermissionDenied()

            # Get date range
            date_from = request.query_params.get(
                "date_from", (timezone.now() - timedelta(days=30)).date()
            )
            date_to = request.query_params.get("date_to", timezone.now().date())

            # Get attendance records
            attendance_records = ClassAttendance.objects.filter(
                school_class=school_class, date__range=[date_from, date_to]
            ).order_by("-date")

            # Calculate statistics
            total_records = attendance_records.count()
            total_students = school_class.students.count()

            if total_records == 0:
                return Response(
                    {
                        "class_name": school_class.name,
                        "total_students": total_students,
                        "average_attendance_rate": 0,
                        "total_records": 0,
                        "recent_records": [],
                    }
                )

            # Calculate average attendance rate
            total_present = sum(
                record.present_students.count() for record in attendance_records
            )
            average_rate = (
                (total_present / (total_records * total_students) * 100)
                if total_students > 0
                else 0
            )

            # Get recent records
            recent_records = []
            for record in attendance_records[:10]:
                present_count = record.present_students.count()
                recent_records.append(
                    {
                        "id": record.id,
                        "date": record.date,
                        "present_count": present_count,
                        "absent_count": total_students - present_count,
                        "attendance_rate": record.attendance_rate,
                        "taken_by": (
                            record.taken_by.get_full_name()
                            if record.taken_by
                            else "System"
                        ),
                        "notes": record.notes,
                    }
                )

            return Response(
                {
                    "class_name": school_class.name,
                    "class_id": school_class.id,
                    "total_students": total_students,
                    "average_attendance_rate": round(average_rate, 2),
                    "total_records": total_records,
                    "recent_records": recent_records,
                }
            )

        except SchoolClass.DoesNotExist:
            return Response(
                {"error": "Class not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
