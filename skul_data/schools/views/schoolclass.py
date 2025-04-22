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

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SchoolClassCreateSerializer
        elif self.action == "promote":
            return SchoolClassPromoteSerializer
        return SchoolClassSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "destroy", "promote", "assign_teacher"]:
            return [IsAdministrator()]
        elif self.action in ["retrieve", "list"]:
            return [IsAuthenticated()]
        return [IsTeacher()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return SchoolClass.objects.none()

        queryset = queryset.filter(school=school)

        # Teachers can only see classes they teach
        if user.user_type == "teacher":
            return queryset.filter(class_teacher=user.teacher_profile)

        return queryset

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
            return Response(
                SchoolClassSerializer(new_class).data, status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def assign_teacher(self, request, pk=None):
        """Assign or change class teacher"""
        class_instance = self.get_object()
        teacher_id = request.data.get("teacher_id")

        if not teacher_id:
            return Response(
                {"error": "teacher_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from users.models import Teacher

            teacher = Teacher.objects.get(id=teacher_id, school=class_instance.school)
            class_instance.class_teacher = teacher
            class_instance.save()
            return Response(
                SchoolClassSerializer(class_instance).data, status=status.HTTP_200_OK
            )
        except Teacher.DoesNotExist:
            return Response(
                {"error": "Teacher not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """Class analytics for dashboard"""
        queryset = self.filter_queryset(self.get_queryset())

        # Basic counts
        total_classes = queryset.count()
        classes_by_level = queryset.values("level").annotate(count=Count("id"))
        classes_by_grade = queryset.values("grade_level").annotate(count=Count("id"))

        # Student distribution
        student_distribution = (
            queryset.annotate(student_count=Count("students"))
            .values("name", "student_count")
            .order_by("-student_count")
        )

        # Performance analytics
        performance_data = (
            queryset.annotate(avg_performance=Avg("students__academic_records__score"))
            .values("name", "avg_performance")
            .order_by("-avg_performance")
        )

        return Response(
            {
                "total_classes": total_classes,
                "classes_by_level": classes_by_level,
                "classes_by_grade": classes_by_grade,
                "student_distribution": student_distribution,
                "performance_data": performance_data,
            }
        )


class ClassTimetableViewSet(viewsets.ModelViewSet):
    queryset = ClassTimetable.objects.all()
    serializer_class = ClassTimetableSerializer
    permission_classes = [IsAdministrator | IsTeacher]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["school_class", "is_active"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return ClassTimetable.objects.none()

        queryset = queryset.filter(school_class__school=school)

        if user.user_type == "teacher":
            return queryset.filter(school_class__class_teacher=user.teacher_profile)

        return queryset


class ClassDocumentViewSet(viewsets.ModelViewSet):
    queryset = ClassDocument.objects.all()
    serializer_class = ClassDocumentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["school_class", "document_type", "created_by"]
    search_fields = ["title", "description"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return ClassDocument.objects.none()

        queryset = queryset.filter(school_class__school=school)

        if user.user_type == "teacher":
            return queryset.filter(
                models.Q(school_class__class_teacher=user.teacher_profile)
                | models.Q(created_by=user)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ClassAttendanceViewSet(viewsets.ModelViewSet):
    queryset = ClassAttendance.objects.all()
    serializer_class = ClassAttendanceSerializer
    permission_classes = [IsAdministrator | IsTeacher]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["school_class", "date", "taken_by"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return ClassAttendance.objects.none()

        queryset = queryset.filter(school_class__school=school)

        if user.user_type == "teacher":
            return queryset.filter(
                models.Q(school_class__class_teacher=user.teacher_profile)
                | models.Q(taken_by=user)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(taken_by=self.request.user)

    @action(detail=True, methods=["post"])
    def mark_attendance(self, request, pk=None):
        attendance = self.get_object()
        student_ids = request.data.get("student_ids", [])

        if not student_ids:
            return Response(
                {"error": "student_ids is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from skul_data.students.models.student import Student

            students = Student.objects.filter(
                id__in=student_ids, school_class=attendance.school_class
            )
            attendance.present_students.set(students)
            return Response(
                ClassAttendanceSerializer(attendance).data, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
