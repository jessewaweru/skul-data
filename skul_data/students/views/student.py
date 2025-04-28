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
        user = self.request.user

        if user.is_superuser:
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
            return queryset.filter(
                Q(teacher=user.teacher_profile)
                | Q(student_class__class_teacher=user.teacher_profile)
            )

        # Parents only see their own children
        elif user.user_type == "parent":
            return queryset.filter(
                Q(parent=user.parent_profile) | Q(guardians=user.parent_profile)
            ).distinct()

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

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)

    def perform_destroy(self, instance):
        """Override delete to perform soft delete"""
        instance.deactivate(reason="Deleted via admin dashboard")
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
        student.promote(new_class)

        return Response(StudentSerializer(student).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        student = self.get_object()
        serializer = StudentTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_school = serializer.validated_data["new_school_id"]
        student.transfer(new_school)

        return Response(StudentSerializer(student).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def graduate(self, request, pk=None):
        student = self.get_object()
        student.graduate()
        return Response({"status": "student graduated"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        student = self.get_object()
        reason = request.data.get("reason", "No reason provided")
        student.deactivate(reason)
        return Response({"status": "student deactivated"}, status=status.HTTP_200_OK)

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

        for row_num, row in enumerate(reader, start=1):
            try:
                # Map CSV row to student data
                student_data = {
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "date_of_birth": row["dob"],
                    "gender": row["gender"],
                    "school": request.user.school.id,
                    "parent": row["parent"],
                    # Add other fields as needed
                }

                # Create student
                student_serializer = StudentCreateSerializer(
                    data=student_data, context={"request": request}
                )
                student_serializer.is_valid(raise_exception=True)
                student_serializer.save()
                created += 1

            except Exception as e:
                errors.append({"row": row_num, "error": str(e), "data": row})

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

        # Age distribution
        age_distribution = (
            queryset.annotate(age=2023 - models.F("date_of_birth__year"))
            .values("age")
            .annotate(count=Count("id"))
            .order_by("age")
        )

        return Response(
            {
                "total_students": total_students,
                "students_by_class": students_by_class,
                "students_by_status": students_by_status,
                "gender_distribution": gender_distribution,
                "performance_distribution": performance_distribution,
                "age_distribution": age_distribution,
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
        user = self.request.user

        if user.is_superuser:
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
        serializer.save(uploaded_by=self.request.user)


class StudentNoteViewSet(viewsets.ModelViewSet):
    queryset = StudentNote.objects.all()
    serializer_class = StudentNoteSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdministrator() | IsTeacher()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
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
        serializer.save(created_by=self.request.user)


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

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "bulk_create",
        ]:
            return [IsAdministrator() | IsTeacher()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
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
        serializer.save(recorded_by=self.request.user)

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

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return Subject.objects.none()

        return queryset.filter(Q(school=school) | Q(school__isnull=True))

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)
