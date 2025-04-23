from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from skul_data.students.models.student import Student, Subject
from skul_data.students.serializers.student import (
    StudentSerializer,
    StudentCreateSerializer,
    SubjectSerializer,
)
from skul_data.users.permissions.permission import IsAdministrator, IsTeacher
from skul_data.students.models.student import StudentDocument, StudentNote
from skul_data.students.serializers.student import StudentDocumentSerializer
from skul_data.students.serializers.student import StudentNoteSerializer
from skul_data.students.serializers.student import (
    StudentPromoteSerializer,
    StudentTransferSerializer,
    StudentBulkCreateSerializer,
)
import django_filters as filters
from django.db.models import Q, Count
from io import TextIOWrapper
import csv


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
    filter_backends = [filters.rest_framework.DjangoFilterBackend]
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
