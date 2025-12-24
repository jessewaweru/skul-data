from rest_framework import viewsets, filters as drf_filters
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from skul_data.students.models.student import Student, Subject
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.serializers.student import (
    StudentSerializer,
    StudentCreateSerializer,
    SubjectSerializer,
)
from skul_data.users.permissions.permission import IsAdministrator, IsTeacher
from skul_data.students.models.student import (
    StudentDocument,
    StudentNote,
    StudentAttendance,
    StudentStatus,
)
from skul_data.students.serializers.student import StudentNoteSerializer
from skul_data.students.serializers.student import (
    StudentPromoteSerializer,
    StudentTransferSerializer,
    StudentBulkCreateSerializer,
    StudentDocumentSerializer,
    StudentAttendanceSerializer,
    BulkAttendanceSerializer,
)
from django.db.models import Q, Count
from io import TextIOWrapper
import csv
from django.utils import timezone
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.users.models.base_user import User
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.action_logs.utils.action_log import log_action
from rest_framework.permissions import OR
from django.db import models
from skul_data.schools.models.school import School


class StudentFilter(filters.FilterSet):
    class_name = filters.CharFilter(
        field_name="student_class__name", lookup_expr="icontains"
    )
    teacher = filters.CharFilter(
        field_name="teacher__user__username", lookup_expr="icontains"
    )
    parent = filters.CharFilter(
        field_name="parent__user__username", lookup_expr="icontains"
    )
    admission_year = filters.NumberFilter(field_name="admission_date__year")
    performance_tier = filters.CharFilter(field_name="performance_tier")
    status = filters.CharFilter(field_name="status")

    class Meta:
        model = Student
        fields = ["student_class", "gender", "status"]


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = StudentFilter
    search_fields = [
        "first_name",
        "last_name",
        "admission_number",
        "parent__user__first_name",
        "parent__user__last_name",
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return StudentCreateSerializer
        return StudentSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "bulk_create",
        ]:
            return [IsAdministrator()]
        elif self.action in ["promote", "transfer", "graduate", "deactivate"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return Student.objects.none()

        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return Student.objects.none()

        queryset = queryset.filter(school=school)

        # Only show active students by default
        if not self.request.query_params.get("show_inactive"):
            queryset = queryset.filter(is_active=True)

        # Teachers only see students in their classes
        if user.user_type == "teacher":
            # Make sure this condition correctly checks for students in classes where
            # the teacher is assigned as the class teacher
            teacher_profile = getattr(user, "teacher_profile", None)
            if teacher_profile:
                queryset = queryset.filter(
                    Q(student_class__class_teacher=teacher_profile)
                )
            else:
                return Student.objects.none()

        # Parents only see their own children
        elif user.user_type == "parent":
            parent_profile = getattr(user, "parent_profile", None)
            if parent_profile:
                queryset = queryset.filter(
                    Q(parent=parent_profile) | Q(guardians=parent_profile)
                ).distinct()
            else:
                return Student.objects.none()

        return queryset

    def update(self, request, *args, **kwargs):
        if "status" in request.data:
            return Response(
                {
                    "detail": "You cannot update status directly. Use promote, graduate, or deactivate endpoints."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if "status" in request.data:
            return Response(
                {
                    "detail": "You cannot update status directly. Use promote, graduate, or deactivate endpoints."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    # Fix for perform_create method in StudentViewSet
    def perform_create(self, serializer):
        instance = serializer.save(school=self.request.user.school)

        # Add logging for student creation
        log_action(
            self.request.user,
            f"POST /students/students/",
            ActionCategory.CREATE,
            instance,
            {"fields_changed": None},  # For create operations
        )

    def perform_destroy(self, instance):
        """Override delete to perform soft delete"""
        instance.deactivate(
            reason="Deleted via admin dashboard", user=self.request.user
        )
        instance.save()

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restore a soft-deleted student"""
        student = self.get_object()
        if student.is_active:
            return Response(
                {"error": "Student is already active"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student.is_active = True
        student.status = StudentStatus.ACTIVE
        student.deleted_at = None
        student.deletion_reason = None
        student.save()

        return Response(StudentSerializer(student).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def promote(self, request, pk=None):
        student = self.get_object()
        serializer = StudentPromoteSerializer(
            data=request.data, context={"student": student}
        )
        serializer.is_valid(raise_exception=True)

        new_class = serializer.validated_data["new_class_id"]
        old_class = student.student_class
        student.promote(new_class)

        log_action(
            request.user,
            f"Promoted student {student} to class {new_class}",
            ActionCategory.UPDATE,
            student,
            {
                "new_class": new_class.id,
                "new_class_name": new_class.name,
                "old_class": old_class.id if old_class else None,
                "old_class_name": old_class.name if old_class else None,
            },
        )

        return Response(StudentSerializer(student).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        student = self.get_object()
        serializer = StudentTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_school = serializer.validated_data["new_school_id"]
        old_school = student.school
        student.transfer(new_school)

        log_action(
            request.user,
            f"Transferred student {student} to school {new_school}",
            ActionCategory.UPDATE,
            student,
            {
                "new_school": new_school.id,
                "new_school_name": new_school.name,
                "old_school": old_school.id,
                "old_school_name": old_school.name,
                "transfer_date": serializer.validated_data["transfer_date"],
                "reason": serializer.validated_data["reason"],
            },
        )

        return Response(StudentSerializer(student).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def graduate(self, request, pk=None):
        student = self.get_object()
        student.graduate()

        log_action(
            request.user,
            f"Graduated student {student}",
            ActionCategory.UPDATE,
            student,
            {"previous_status": StudentStatus.ACTIVE},
        )

        return Response({"status": "student graduated"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        student = self.get_object()
        reason = request.data.get("reason", "No reason provided")
        previous_status = student.status

        # Deactivate the student without automatic logging from the model
        student.deactivate(reason, user=None)  # Don't log from model

        # Log from the viewset with the expected message format
        log_action(
            request.user,
            f"Deactivated student {student}",
            ActionCategory.UPDATE,
            student,
            {
                "previous_status": previous_status,
                "reason": reason,
                "deletion_reason": student.deletion_reason,
            },
        )

        return Response({"status": "student deactivated"}, status=status.HTTP_200_OK)

    # Fix for bulk_create method
    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        serializer = StudentBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        csv_file = TextIOWrapper(
            serializer.validated_data["file"].file, encoding="utf-8"
        )
        reader = csv.DictReader(csv_file)

        created = 0
        errors = []
        row_num = 0

        for row_num, row in enumerate(reader, start=1):
            try:
                # Map CSV row to student data - Remove school from data
                # Let the serializer handle school assignment
                student_data = {
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "date_of_birth": row["date_of_birth"],
                    "gender": row["gender"],
                    "parent_id": row["parent_id"],
                    # Don't include school here - let perform_create handle it
                }

                # Create student with proper context - but don't use perform_create
                # to avoid individual logging for each student
                student_serializer = StudentCreateSerializer(
                    data=student_data, context={"request": request}
                )
                student_serializer.is_valid(raise_exception=True)
                # Save directly with school assignment
                student_serializer.save(school=request.user.school)
                created += 1

            except Exception as e:
                errors.append({"row": row_num, "error": str(e), "data": row})

        # Log the bulk create action
        log_action(
            request.user,
            f"Bulk created {created} students via CSV",
            ActionCategory.CREATE,
            None,
            {
                "created_count": created,
                "error_count": len(errors),
                "total_rows": row_num,
                "errors": errors[:10],  # Log first 10 errors to avoid huge logs
            },
        )

        return Response(
            {"created": created, "errors": errors, "total_rows": row_num},
            status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        # Basic counts
        total_students = queryset.count()

        students_by_class = queryset.values("student_class__name").annotate(
            count=Count("id")
        )

        students_by_status = queryset.values("status").annotate(count=Count("id"))

        gender_distribution = queryset.values("gender").annotate(count=Count("id"))

        # Performance analytics
        performance_distribution = queryset.values("performance_tier").annotate(
            count=Count("id")
        )

        # Age distribution - Fixed to use current year dynamically
        from django.utils import timezone

        current_year = timezone.now().year

        age_distribution = (
            queryset.annotate(age=current_year - models.F("date_of_birth__year"))
            .values("age")
            .annotate(count=Count("id"))
            .order_by("age")
        )

        return Response(
            {
                "total_students": total_students,
                "students_by_class": list(students_by_class),
                "students_by_status": list(students_by_status),
                "gender_distribution": list(gender_distribution),
                "performance_distribution": list(performance_distribution),
                "age_distribution": list(age_distribution),
            }
        )


class StudentDocumentViewSet(viewsets.ModelViewSet):
    queryset = StudentDocument.objects.all()
    serializer_class = StudentDocumentSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return StudentDocument.objects.none()
        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            return queryset

        # Filter by student's school
        queryset = queryset.filter(student__school=user.school)

        # Teachers only see documents for their students
        if user.user_type == "teacher":
            return queryset.filter(
                Q(student__teacher=user.teacher_profile)
                | Q(student__student_class__class_teacher=user.teacher_profile)
            )

        # Parents only see documents for their children
        elif user.user_type == "parent":
            return queryset.filter(
                Q(student__parent=user.parent_profile)
                | Q(student__guardians=user.parent_profile)
            ).distinct()

        return queryset

    def perform_create(self, serializer):
        instance = serializer.save(uploaded_by=self.request.user)
        log_action(
            self.request.user,
            f"Uploaded document '{instance.title}' ({instance.document_type}) for student {instance.student}",
            ActionCategory.UPLOAD,
            instance,
            {
                "student_id": instance.student.id,
                "student_name": instance.student.full_name,
                "document_type": instance.document_type,
                "file_size": instance.file.size if instance.file else 0,
            },
        )


class StudentNoteViewSet(viewsets.ModelViewSet):
    queryset = StudentNote.objects.all()
    serializer_class = StudentNoteSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [OR(IsAdministrator(), IsTeacher())]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return StudentNote.objects.none()

        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            return queryset

        # Filter by student's school
        queryset = queryset.filter(student__school=user.school)

        # Teachers only see notes they created or for their students
        if user.user_type == "teacher":
            return queryset.filter(
                Q(created_by=user)
                | Q(student__teacher=user.teacher_profile)
                | Q(student__student_class__class_teacher=user.teacher_profile)
            )

        # Parents only see non-private notes for their children
        elif user.user_type == "parent":
            return queryset.filter(
                (
                    Q(student__parent=user.parent_profile)
                    | Q(student__guardians=user.parent_profile)
                ),
                is_private=False,
            ).distinct()

        return queryset

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        log_action(
            self.request.user,
            f"Added {instance.note_type} note for student {instance.student}",
            ActionCategory.CREATE,
            instance,
            {
                "student_id": instance.student.id,
                "student_name": instance.student.full_name,
                "note_type": instance.note_type,
                "is_private": instance.is_private,
            },
        )

    def perform_update(self, serializer):
        old_note = self.get_object()
        instance = serializer.save()
        log_action(
            self.request.user,
            f"Updated note for student {instance.student}",
            ActionCategory.UPDATE,
            instance,
            {
                "student_id": instance.student.id,
                "student_name": instance.student.full_name,
                "note_type": instance.note_type,
                "changes": {
                    field: {
                        "old": getattr(old_note, field),
                        "new": getattr(instance, field),
                    }
                    for field in serializer.validated_data.keys()
                },
            },
        )


class StudentAttendanceFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")
    student_name = filters.CharFilter(method="filter_by_student_name")
    class_id = filters.NumberFilter(field_name="student__student_class")

    class Meta:
        model = StudentAttendance
        fields = ["student", "date", "status"]

    def filter_by_student_name(self, queryset, name, value):
        return queryset.filter(
            Q(student__first_name__icontains=value)
            | Q(student__last_name__icontains=value)
        )


class StudentAttendanceViewSet(viewsets.ModelViewSet):
    queryset = StudentAttendance.objects.all()
    serializer_class = StudentAttendanceSerializer
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter]
    filterset_class = StudentAttendanceFilter
    search_fields = ["student__first_name", "student__last_name", "notes", "reason"]

    # def get_permissions(self):
    #     if self.action in [
    #         "create",
    #         "update",
    #         "partial_update",
    #         "destroy",
    #         "bulk_create",
    #     ]:
    #         return [
    #             IsAdministrator(),
    #             IsTeacher(),
    #         ]
    #     return [IsAuthenticated()]

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "bulk_create",
        ]:
            # IMPORTANT FIX: Changed to allow any of these permissions
            permission_classes = [IsAdministrator | IsTeacher]
            return [permission() for permission in permission_classes]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return Student.objects.none()

        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return StudentAttendance.objects.none()

        queryset = queryset.filter(student__school=school)

        # Teachers see attendance for their class or assigned students
        if user.user_type == "teacher":
            return queryset.filter(
                Q(student__teacher=user.teacher_profile)
                | Q(student__student_class__class_teacher=user.teacher_profile)
            )

        # Parents see attendance for their children
        elif user.user_type == "parent":
            return queryset.filter(
                Q(student__parent=user.parent_profile)
                | Q(student__guardians=user.parent_profile)
            ).distinct()

        return queryset

    def perform_create(self, serializer):
        instance = serializer.save(recorded_by=self.request.user)
        log_action(
            self.request.user,
            f"Recorded attendance for {instance.student} as {instance.status}",
            ActionCategory.UPDATE,
            instance,
            {
                "student_id": instance.student.id,
                "student_name": instance.student.full_name,
                "date": instance.date.isoformat(),
                "status": instance.status,
                "reason": instance.reason,
                "time_in": str(instance.time_in) if instance.time_in else None,
            },
        )

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        serializer = BulkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        date = serializer.validated_data["date"]
        student_statuses = serializer.validated_data["student_statuses"]

        created = 0
        updated = 0
        errors = []

        for student_status in student_statuses:
            try:
                student_id = student_status["student_id"]
                status = student_status["status"]
                reason = student_status.get("reason")
                time_in = student_status.get("time_in")

                # Check if student exists and belongs to user's school
                try:
                    student = Student.objects.get(
                        id=student_id, school=request.user.school
                    )
                except Student.DoesNotExist:
                    errors.append(
                        {
                            "student_id": student_id,
                            "error": "Student not found or not in your school",
                        }
                    )
                    continue

                # Try to update existing attendance record or create new one
                attendance, is_new = StudentAttendance.objects.update_or_create(
                    student=student,
                    date=date,
                    defaults={
                        "status": status,
                        "reason": reason,
                        "time_in": time_in,
                        "recorded_by": request.user,
                    },
                )

                if is_new:
                    created += 1
                else:
                    updated += 1

            except Exception as e:
                errors.append(
                    {"student_id": student_status.get("student_id"), "error": str(e)}
                )
        log_action(
            request.user,
            f"Recorded bulk attendance for {date} - {created} created, {updated} updated",
            ActionCategory.UPDATE,
            None,
            {
                "date": date.isoformat(),
                "created_count": created,
                "updated_count": updated,
                "error_count": len(errors),
                "class_id": serializer.validated_data.get("class_id"),
            },
        )

        return Response({"created": created, "updated": updated, "errors": errors})

    @action(detail=False, methods=["get"])
    def class_attendance(self, request):
        """Get attendance for an entire class on a specific date"""
        date = request.query_params.get("date", timezone.now().date())
        class_id = request.query_params.get("class_id")

        if not class_id:
            return Response(
                {"detail": "class_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if class exists and belongs to user's school
        try:
            school_class = SchoolClass.objects.get(
                id=class_id, school=request.user.school
            )
        except SchoolClass.DoesNotExist:
            return Response(
                {"detail": "Class not found or not in your school"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all students in the class
        students = Student.objects.filter(
            student_class=school_class, status=StudentStatus.ACTIVE
        )

        # Get attendance records for this date
        attendance_records = StudentAttendance.objects.filter(
            student__in=students, date=date
        )

        # Create attendance data
        result = []
        for student in students:
            attendance = attendance_records.filter(student=student).first()
            result.append(
                {
                    "student_id": student.id,
                    "student_name": student.full_name,
                    "status": attendance.status if attendance else None,
                    "reason": attendance.reason if attendance else None,
                    "time_in": attendance.time_in if attendance else None,
                    "has_record": attendance is not None,
                }
            )

        return Response(result)

    @action(detail=False, methods=["get"])
    def student_history(self, request):
        """Get attendance history for a specific student"""
        student_id = request.query_params.get("student_id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to", timezone.now().date())

        if not student_id:
            return Response(
                {"detail": "student_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if student exists and belongs to user's school
        try:
            student = Student.objects.get(id=student_id, school=request.user.school)
        except Student.DoesNotExist:
            return Response(
                {"detail": "Student not found or not in your school"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build filter
        filters = {"student": student}
        if date_from:
            filters["date__gte"] = date_from
        if date_to:
            filters["date__lte"] = date_to

        # Get attendance records
        attendance_records = StudentAttendance.objects.filter(**filters).order_by(
            "date"
        )
        serializer = self.get_serializer(attendance_records, many=True)

        # Calculate statistics
        total_days = attendance_records.count()
        present_days = attendance_records.filter(
            status=AttendanceStatus.PRESENT
        ).count()
        absent_days = attendance_records.filter(status=AttendanceStatus.ABSENT).count()
        late_days = attendance_records.filter(status=AttendanceStatus.LATE).count()
        excused_days = attendance_records.filter(
            status=AttendanceStatus.EXCUSED
        ).count()

        attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0

        return Response(
            {
                "student": {
                    "id": student.id,
                    "name": student.full_name,
                    "class": (
                        student.student_class.name if student.student_class else None
                    ),
                },
                "attendance_records": serializer.data,
                "statistics": {
                    "total_days": total_days,
                    "present_days": present_days,
                    "absent_days": absent_days,
                    "late_days": late_days,
                    "excused_days": excused_days,
                    "attendance_rate": attendance_rate,
                },
            }
        )

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """Get attendance analytics"""
        queryset = self.filter_queryset(self.get_queryset())

        # Get date range from query params or use last 30 days
        date_from = request.query_params.get(
            "date_from", (timezone.now() - timedelta(days=30)).date()
        )
        date_to = request.query_params.get("date_to", timezone.now().date())

        # Filter by date range
        queryset = queryset.filter(date__range=[date_from, date_to])

        # Overall attendance stats
        total_records = queryset.count()
        status_counts = queryset.values("status").annotate(count=Count("id"))

        # Attendance by class
        attendance_by_class = (
            queryset.values("student__student_class__name")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(status=AttendanceStatus.PRESENT)),
                absent=Count("id", filter=Q(status=AttendanceStatus.ABSENT)),
                late=Count("id", filter=Q(status=AttendanceStatus.LATE)),
                excused=Count("id", filter=Q(status=AttendanceStatus.EXCUSED)),
            )
            .order_by("student__student_class__name")
        )

        # Calculate attendance rates
        for entry in attendance_by_class:
            entry["attendance_rate"] = (
                (entry["present"] / entry["total"]) * 100 if entry["total"] > 0 else 0
            )

        # Daily attendance trend
        daily_trend = (
            queryset.values("date")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(status=AttendanceStatus.PRESENT)),
                absent=Count("id", filter=Q(status=AttendanceStatus.ABSENT)),
                late=Count("id", filter=Q(status=AttendanceStatus.LATE)),
                excused=Count("id", filter=Q(status=AttendanceStatus.EXCUSED)),
            )
            .order_by("date")
        )

        # Calculate daily attendance rates
        for entry in daily_trend:
            entry["attendance_rate"] = (
                (entry["present"] / entry["total"]) * 100 if entry["total"] > 0 else 0
            )
            # Convert date to string for JSON serialization
            entry["date"] = entry["date"].isoformat()

        return Response(
            {
                "total_records": total_records,
                "status_counts": status_counts,
                "attendance_by_class": attendance_by_class,
                "daily_trend": daily_trend,
            }
        )


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["school"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        school_id = self.request.query_params.get("school")
        school_code = self.request.query_params.get("school_code")

        # Try to get school by ID first, then by code
        if school_id:
            try:
                return queryset.filter(school_id=school_id)
            except (ValueError, School.DoesNotExist):
                return queryset.none()
        elif school_code:
            try:
                return queryset.filter(school__code=school_code)
            except School.DoesNotExist:
                return queryset.none()

        # If user is authenticated and has a school, filter by their school
        user = self.request.user
        if user.is_authenticated:
            if (
                hasattr(user, "school_admin_profile")
                and user.school_admin_profile.school
            ):
                return queryset.filter(school=user.school_admin_profile.school)
            elif (
                hasattr(user, "administrator_profile")
                and user.administrator_profile.school
            ):
                return queryset.filter(school=user.administrator_profile.school)

        return queryset.none()

    def perform_create(self, serializer):
        # Get school from user or request data
        school = None
        if hasattr(self.request.user, "school_admin_profile"):
            school = self.request.user.school_admin_profile.school
        elif hasattr(self.request.user, "administrator_profile"):
            school = self.request.user.administrator_profile.school

        # If school is provided in request data, use that
        school_id = self.request.data.get("school")
        if school_id and not school:
            try:
                school = School.objects.get(id=school_id)
            except School.DoesNotExist:
                pass

        instance = serializer.save(school=school)
        log_action(
            self.request.user,
            f"Created new subject {instance.name}",
            ActionCategory.CREATE,
            instance,
            {
                "school_id": instance.school.id if instance.school else None,
                "school_name": instance.school.name if instance.school else None,
                "code": instance.code,
            },
        )

    def perform_update(self, serializer):
        old_subject = self.get_object()
        instance = serializer.save()
        log_action(
            self.request.user,
            f"Updated subject {instance.name}",
            ActionCategory.UPDATE,
            instance,
            {
                "changes": {
                    field: {
                        "old": getattr(old_subject, field),
                        "new": getattr(instance, field),
                    }
                    for field in serializer.validated_data.keys()
                }
            },
        )

    def perform_destroy(self, instance):
        log_action(
            self.request.user,
            f"Deleted subject {instance.name}",
            ActionCategory.DELETE,
            None,
            {
                "subject_id": instance.id,
                "subject_name": instance.name,
                "code": instance.code,
            },
        )
        instance.delete()
