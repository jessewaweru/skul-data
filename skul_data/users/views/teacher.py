from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from skul_data.users.models.teacher import (
    Teacher,
    TeacherWorkload,
    TeacherAttendance,
    TeacherDocument,
)
from skul_data.users.serializers.teacher import (
    TeacherSerializer,
    TeacherCreateSerializer,
    TeacherStatusChangeSerializer,
    TeacherAssignmentSerializer,
    TeacherSubjectAssignmentSerializer,
    TeacherWorkloadSerializer,
    TeacherAttendanceSerializer,
    TeacherDocumentSerializer,
)
from skul_data.users.permissions.permission import IsAdministrator, IsTeacher


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "school",
        "status",
        "is_class_teacher",
        "is_department_head",
        "subjects_taught",
        "assigned_classes",
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "qualification",
        "specialization",
        "payroll_number",
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return TeacherCreateSerializer
        return TeacherSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "change_status",
            "assign_classes",
            "assign_subjects",
        ]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return Teacher.objects.none()

        queryset = queryset.filter(school=school)

        # Teachers can only see their own profile
        if user.user_type == "teacher":
            return queryset.filter(user=user)

        return queryset.select_related("user", "school").prefetch_related(
            "subjects_taught", "assigned_classes"
        )

    def perform_create(self, serializer):
        school = self.request.user.school
        serializer.save(school=school)

    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        teacher = self.get_object()
        serializer = TeacherStatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        teacher.status = serializer.validated_data["status"]
        if teacher.status == "TERMINATED":
            teacher.termination_date = serializer.validated_data["termination_date"]
        teacher.save()

        return Response(TeacherSerializer(teacher).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def assign_classes(self, request, pk=None):
        teacher = self.get_object()
        serializer = TeacherAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        classes = serializer.validated_data["class_ids"]
        action = serializer.validated_data["action"]

        if action == "ADD":
            teacher.assigned_classes.add(*classes)
        elif action == "REMOVE":
            teacher.assigned_classes.remove(*classes)
        elif action == "REPLACE":
            teacher.assigned_classes.set(classes)

        return Response(TeacherSerializer(teacher).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def assign_subjects(self, request, pk=None):
        teacher = self.get_object()
        serializer = TeacherSubjectAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subjects = serializer.validated_data["subject_ids"]
        action = serializer.validated_data["action"]

        if action == "ADD":
            teacher.subjects_taught.add(*subjects)
        elif action == "REMOVE":
            teacher.subjects_taught.remove(*subjects)
        elif action == "REPLACE":
            teacher.subjects_taught.set(subjects)

        return Response(TeacherSerializer(teacher).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        # Basic counts
        total_teachers = queryset.count()
        teachers_by_status = queryset.values("status").annotate(count=Count("id"))

        # Experience distribution
        experience_distribution = (
            queryset.values("years_of_experience")
            .annotate(count=Count("id"))
            .order_by("years_of_experience")
        )

        # Class assignments
        class_assignments = (
            queryset.annotate(class_count=Count("assigned_classes"))
            .values("class_count")
            .annotate(teacher_count=Count("id"))
            .order_by("class_count")
        )

        # Subject distribution
        subject_distribution = (
            queryset.annotate(subject_count=Count("subjects_taught"))
            .values("subject_count")
            .annotate(teacher_count=Count("id"))
            .order_by("subject_count")
        )

        return Response(
            {
                "total_teachers": total_teachers,
                "teachers_by_status": teachers_by_status,
                "experience_distribution": experience_distribution,
                "class_assignments": class_assignments,
                "subject_distribution": subject_distribution,
            }
        )


class TeacherWorkloadViewSet(viewsets.ModelViewSet):
    queryset = TeacherWorkload.objects.all()
    serializer_class = TeacherWorkloadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["teacher", "school_class", "subject", "term", "school_year"]
    permission_classes = [IsAdministrator | IsTeacher]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return TeacherWorkload.objects.none()

        queryset = queryset.filter(teacher__school=school)

        if user.user_type == "teacher":
            return queryset.filter(teacher__user=user)

        return queryset


class TeacherAttendanceViewSet(viewsets.ModelViewSet):
    queryset = TeacherAttendance.objects.all()
    serializer_class = TeacherAttendanceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["teacher", "date", "status"]
    permission_classes = [IsAdministrator]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return TeacherAttendance.objects.none()

        return queryset.filter(teacher__school=school)


class TeacherDocumentViewSet(viewsets.ModelViewSet):
    queryset = TeacherDocument.objects.all()
    serializer_class = TeacherDocumentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["teacher", "document_type", "is_confidential"]
    search_fields = ["title", "description"]

    def get_permissions(self):
        if self.action in ["create", "update", "destroy"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return TeacherDocument.objects.none()

        queryset = queryset.filter(teacher__school=school)

        if user.user_type == "teacher":
            return queryset.filter(Q(teacher__user=user) | Q(is_confidential=False))

        return queryset

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
