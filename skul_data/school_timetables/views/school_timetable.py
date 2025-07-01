from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from skul_data.school_timetables.models.school_timetable import (
    TimeSlot,
    TimetableStructure,
    Timetable,
    Lesson,
    TimetableConstraint,
    SubjectGroup,
    TeacherAvailability,
)
from skul_data.school_timetables.serializers.school_timetable import (
    TimeSlotSerializer,
    TimetableStructureSerializer,
    TimetableSerializer,
    LessonSerializer,
    TimetableConstraintSerializer,
    SubjectGroupSerializer,
    TeacherAvailabilitySerializer,
    TimetableGenerateSerializer,
    TimetableCloneSerializer,
)
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.teacher import Teacher
from skul_data.users.permissions.permission import HasRolePermission
from rest_framework.permissions import IsAuthenticated
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
import random
from django.core.exceptions import PermissionDenied
from skul_data.users.models.base_user import User


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["school", "day_of_week", "is_break", "is_active"]
    search_fields = ["name", "break_name"]
    required_permission = "manage_timetable_settings"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            return queryset.filter(school=user.school_admin_profile.school)
        elif hasattr(user, "administrator_profile"):
            return queryset.filter(school=user.administrator_profile.school)

        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            school = user.school_admin_profile.school
        elif hasattr(user, "administrator_profile"):
            school = user.administrator_profile.school
        else:
            raise PermissionDenied("You don't have permission")
        serializer.save(school=school)


class TimetableStructureViewSet(viewsets.ModelViewSet):
    queryset = TimetableStructure.objects.all()
    serializer_class = TimetableStructureSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_timetable_settings"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            return queryset.filter(school=user.school_admin_profile.school)
        elif hasattr(user, "administrator_profile"):
            return queryset.filter(school=user.administrator_profile.school)

        return queryset.none()

    @action(detail=True, methods=["post"])
    def generate_slots(self, request, pk=None):
        structure = self.get_object()
        structure.generate_time_slots()
        return Response(
            {"status": "Time slots generated successfully"}, status=status.HTTP_200_OK
        )


class TimetableViewSet(viewsets.ModelViewSet):
    queryset = Timetable.objects.all()
    serializer_class = TimetableSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["school_class", "academic_year", "term", "is_active"]
    search_fields = ["school_class__name"]
    required_permission_get = "view_timetables"
    required_permission_post = "manage_timetables"
    required_permission_put = "manage_timetables"
    required_permission_delete = "manage_timetables"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            school = user.school_admin_profile.school
        elif hasattr(user, "administrator_profile"):
            school = user.administrator_profile.school
        else:
            return Timetable.objects.none()

        queryset = queryset.filter(school_class__school=school)

        # Teachers can only see timetables for their classes
        if user.user_type == "teacher":
            teacher_classes = user.teacher_profile.assigned_classes.values_list(
                "id", flat=True
            )
            queryset = queryset.filter(school_class__in=teacher_classes)

        return queryset.select_related("school_class").prefetch_related("lessons")

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        timetable = self.get_object()

        # Deactivate any other active timetables for this class
        Timetable.objects.filter(
            school_class=timetable.school_class, is_active=True
        ).exclude(pk=timetable.pk).update(is_active=False)

        timetable.is_active = True
        timetable.save()

        log_action(
            user=request.user,
            action=f"Activated timetable for {timetable.school_class}",
            category=ActionCategory.UPDATE,
            obj=timetable,
            metadata={"academic_year": timetable.academic_year, "term": timetable.term},
        )

        return Response(TimetableSerializer(timetable).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = TimetableGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        class_ids = data["school_class_ids"]
        academic_year = data["academic_year"]
        term = data["term"]
        regenerate = data["regenerate_existing"]
        apply_constraints = data["apply_constraints"]

        # Get the classes
        classes = SchoolClass.objects.filter(id__in=class_ids)
        if classes.count() != len(class_ids):
            return Response(
                {"error": "One or more class IDs are invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if timetables already exist
        existing_timetables = Timetable.objects.filter(
            school_class__in=classes, academic_year=academic_year, term=term
        )

        if existing_timetables.exists() and not regenerate:
            return Response(
                {"error": "Timetables already exist for these classes in this term"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delete existing if regenerating
        if regenerate:
            existing_timetables.delete()

        # Generate timetables
        timetables = []
        for school_class in classes:
            timetable = self._generate_timetable(
                school_class, academic_year, term, apply_constraints
            )
            timetables.append(timetable)

        log_action(
            user=request.user,
            action=f"Generated timetables for {len(timetables)} classes",
            category=ActionCategory.CREATE,
            metadata={
                "class_ids": class_ids,
                "academic_year": academic_year,
                "term": term,
                "apply_constraints": apply_constraints,
            },
        )

        return Response(
            TimetableSerializer(timetables, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    def _generate_timetable(self, school_class, academic_year, term, apply_constraints):
        """Generate a timetable for a single class"""
        # Create the timetable
        timetable = Timetable.objects.create(
            school_class=school_class,
            academic_year=academic_year,
            term=term,
            is_active=False,
        )

        # Get the school's timetable structure
        structure = TimetableStructure.objects.get(school=school_class.school)
        time_slots = TimeSlot.objects.filter(
            school=school_class.school, is_break=False
        ).order_by("day_of_week", "order")

        # Get all subjects for the class
        subjects = school_class.subjects.all()

        # Get teachers for each subject
        subject_teachers = {}
        for subject in subjects:
            teachers = Teacher.objects.filter(
                subjects_taught=subject, assigned_classes=school_class
            )
            if teachers.exists():
                subject_teachers[subject.id] = list(teachers)

        # Apply constraints if requested
        constraints = []
        if apply_constraints:
            constraints = TimetableConstraint.objects.filter(
                school=school_class.school, is_active=True
            )

        # Simple random scheduling (replace with proper algorithm)
        scheduled_lessons = []
        for time_slot in time_slots:
            # Skip if no subjects left
            if not subjects:
                break

            # Get available subjects (those not yet fully scheduled)
            available_subjects = [
                subj
                for subj in subjects
                if subj.periods_per_week
                > Lesson.objects.filter(timetable=timetable, subject=subj).count()
            ]

            if not available_subjects:
                continue

            # Randomly select a subject
            subject = random.choice(available_subjects)

            # Get available teachers for this subject
            available_teachers = subject_teachers.get(subject.id, [])
            if not available_teachers:
                continue

            teacher = random.choice(available_teachers)

            # Check for teacher clashes
            teacher_clash = Lesson.objects.filter(
                timetable__school_class__school=school_class.school,
                time_slot=time_slot,
                teacher=teacher,
            ).exists()

            if teacher_clash:
                continue

            # Create the lesson
            lesson = Lesson.objects.create(
                timetable=timetable,
                subject=subject,
                teacher=teacher,
                time_slot=time_slot,
            )
            scheduled_lessons.append(lesson)

        return timetable

    @action(detail=False, methods=["post"])
    def clone(self, request):
        serializer = TimetableCloneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        class_ids = data["school_class_ids"]
        source_year = data["source_academic_year"]
        source_term = data["source_term"]
        target_year = data["target_academic_year"]
        target_term = data["target_term"]

        # Get the source timetables
        source_timetables = Timetable.objects.filter(
            school_class__id__in=class_ids, academic_year=source_year, term=source_term
        )

        if source_timetables.count() != len(class_ids):
            return Response(
                {"error": "Not all classes have source timetables"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if target timetables already exist
        existing_targets = Timetable.objects.filter(
            school_class__id__in=class_ids, academic_year=target_year, term=target_term
        )
        if existing_targets.exists():
            return Response(
                {"error": "Target timetables already exist for some classes"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Clone the timetables
        cloned_timetables = []
        for source in source_timetables:
            # Create new timetable
            new_timetable = Timetable.objects.create(
                school_class=source.school_class,
                academic_year=target_year,
                term=target_term,
                is_active=False,
            )

            # Clone lessons
            for lesson in source.lessons.all():
                Lesson.objects.create(
                    timetable=new_timetable,
                    subject=lesson.subject,
                    teacher=lesson.teacher,
                    time_slot=lesson.time_slot,
                    is_double_period=lesson.is_double_period,
                    room=lesson.room,
                    notes=lesson.notes,
                )

            cloned_timetables.append(new_timetable)

        log_action(
            user=request.user,
            action=f"Cloned {len(cloned_timetables)} timetables from {source_year} Term {source_term} to {target_year} Term {target_term}",
            category=ActionCategory.CREATE,
            metadata={
                "source_year": source_year,
                "source_term": source_term,
                "target_year": target_year,
                "target_term": target_term,
                "class_ids": class_ids,
            },
        )

        return Response(
            TimetableSerializer(cloned_timetables, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        """Export timetable as CSV/PDF/Excel"""
        timetable = self.get_object()
        format = request.query_params.get("format", "csv")

        # TODO: Implement export functionality
        return Response(
            {"status": "Export functionality coming soon"},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["timetable", "subject", "teacher", "time_slot"]
    required_permission_get = "view_timetables"
    required_permission_post = "manage_timetables"
    required_permission_put = "manage_timetables"
    required_permission_delete = "manage_timetables"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            school = user.school_admin_profile.school
        elif hasattr(user, "administrator_profile"):
            school = user.administrator_profile.school
        else:
            return Lesson.objects.none()

        queryset = queryset.filter(timetable__school_class__school=school)

        # Teachers can only see their own lessons
        if user.user_type == "teacher":
            queryset = queryset.filter(teacher=user.teacher_profile)

        return queryset.select_related("timetable", "subject", "teacher", "time_slot")


class TimetableConstraintViewSet(viewsets.ModelViewSet):
    queryset = TimetableConstraint.objects.all()
    serializer_class = TimetableConstraintSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["school", "constraint_type", "is_hard_constraint", "is_active"]
    search_fields = ["description"]
    required_permission = "manage_timetable_settings"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            return queryset.filter(school=user.school_admin_profile.school)
        elif hasattr(user, "administrator_profile"):
            return queryset.filter(school=user.administrator_profile.school)

        return queryset.none()


class SubjectGroupViewSet(viewsets.ModelViewSet):
    queryset = SubjectGroup.objects.all()
    serializer_class = SubjectGroupSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["school"]
    search_fields = ["name", "description"]
    required_permission = "manage_timetable_settings"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            return queryset.filter(school=user.school_admin_profile.school)
        elif hasattr(user, "administrator_profile"):
            return queryset.filter(school=user.administrator_profile.school)

        return queryset.none()


class TeacherAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = TeacherAvailability.objects.all()
    serializer_class = TeacherAvailabilitySerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["teacher", "day_of_week", "is_available"]
    required_permission = "manage_timetable_settings"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            school = user.school_admin_profile.school
        elif hasattr(user, "administrator_profile"):
            school = user.administrator_profile.school
        else:
            return TeacherAvailability.objects.none()

        # Filter by teachers in the same school
        teacher_ids = Teacher.objects.filter(school=school).values_list("id", flat=True)
        return queryset.filter(teacher__in=teacher_ids)

    @action(detail=False, methods=["get"])
    def bulk_update_form(self, request):
        """Return form data for bulk updating teacher availability"""
        user = request.user

        if user.user_type == "school_admin":
            school = user.school_admin_profile.school
        elif hasattr(user, "administrator_profile"):
            school = user.administrator_profile.school
        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        # Get all teachers
        teachers = Teacher.objects.filter(school=school)
        teacher_options = [
            {"value": t.id, "label": t.user.get_full_name()} for t in teachers
        ]

        # Get all days
        day_options = [
            {"value": day[0], "label": day[1]} for day in TimeSlot.DAYS_OF_WEEK
        ]

        return Response({"teachers": teacher_options, "days": day_options})

    @action(detail=False, methods=["post"])
    def bulk_update(self, request):
        """Bulk update teacher availability"""
        updates = request.data.get("updates", [])

        if not updates:
            return Response(
                {"error": "No updates provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Validate and process updates
        results = {"success": 0, "errors": []}
        for update in updates:
            teacher_id = update.get("teacher_id")
            day = update.get("day_of_week")
            is_available = update.get("is_available", True)
            available_from = update.get("available_from")
            available_to = update.get("available_to")
            reason = update.get("reason", "")

            try:
                teacher = Teacher.objects.get(id=teacher_id)
                availability, created = TeacherAvailability.objects.update_or_create(
                    teacher=teacher,
                    day_of_week=day,
                    defaults={
                        "is_available": is_available,
                        "available_from": available_from,
                        "available_to": available_to,
                        "reason": reason,
                    },
                )
                results["success"] += 1
            except Exception as e:
                results["errors"].append(
                    {"teacher_id": teacher_id, "day": day, "error": str(e)}
                )

        log_action(
            user=request.user,
            action="Bulk updated teacher availability",
            category=ActionCategory.UPDATE,
            metadata={
                "updates_count": len(updates),
                "success_count": results["success"],
                "error_count": len(results["errors"]),
            },
        )

        return Response(results, status=status.HTTP_200_OK)
