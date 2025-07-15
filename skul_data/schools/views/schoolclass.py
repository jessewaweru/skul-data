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

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """Class analytics for dashboard"""
        # Log the analytics view
        # Log the analytics view
        log_action(
            user=request.user,
            action="Viewed class analytics",
            category=ActionCategory.VIEW,
            metadata={"path": request.path, "query_params": dict(request.GET)},
        )

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

        # Get the user's school
        school = None
        if user.user_type == User.SCHOOL_ADMIN:
            try:
                school = user.schooladmin.school
            except AttributeError:
                return ClassDocument.objects.none()
        elif hasattr(user, "school"):
            school = user.school

        if not school:
            return ClassDocument.objects.none()

        # Filter by school
        queryset = queryset.filter(school_class__school=school)

        # Teachers can only see documents for classes they teach
        if user.user_type == "teacher":
            return queryset.filter(
                models.Q(school_class__class_teacher=user.teacher_profile)
                | models.Q(created_by=user)
            )

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
    # permission_classes = [IsAuthenticated, HasRolePermission]

    # UPDATED PERMISSIONS:
    def get_permissions(self):
        if self.action == "mark_attendance":
            # Allow teachers to mark attendance for their classes
            return [IsAuthenticated(), HasRolePermission()]
        return [IsAuthenticated(), HasRolePermission()]

    # Set specific permissions
    required_permission_get = "view_attendance"
    required_permission_post = "manage_attendance"
    required_permission_put = "manage_attendance"
    required_permission_delete = "manage_attendance"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return ClassAttendance.objects.none()

        queryset = queryset.filter(school_class__school=school)

        if user.user_type == User.TEACHER:
            # UPDATED: Allow teachers to see attendance for their classes
            return queryset.filter(
                models.Q(school_class__class_teacher=user.teacher_profile)
                | models.Q(taken_by=user)
            )

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        school_class = serializer.validated_data.get("school_class")

        # Additional check for teachers
        if (
            user.user_type == "teacher"
            and school_class.class_teacher != user.teacher_profile
        ):
            raise PermissionDenied(
                "You can only take attendance for your assigned classes"
            )

        serializer.save(taken_by=user)

    @action(detail=True, methods=["post"])
    def mark_attendance(self, request, pk=None):
        attendance = self.get_object()
        student_ids = request.data.get("student_ids", [])

        # ADDED: Check if teacher can mark attendance for this class
        if (
            request.user.user_type == User.TEACHER
            and attendance.school_class.class_teacher != request.user.teacher_profile
        ):
            raise PermissionDenied(
                "You can only mark attendance for your assigned classes"
            )

        try:
            attendance._current_user = request.user
            attendance.update_attendance(student_ids, user=request.user)

            # Log the action
            log_action(
                user=request.user,
                action="Marked attendance",
                category=ActionCategory.UPDATE,
                obj=attendance,
                metadata={
                    "total_present": len(student_ids),
                    "student_ids": student_ids,
                },
            )

            return Response(
                ClassAttendanceSerializer(attendance).data, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
