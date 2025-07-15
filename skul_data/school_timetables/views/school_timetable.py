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
        """Generate a timetable for a single class with constraints"""
        # Create the timetable
        timetable = Timetable.objects.create(
            school_class=school_class,
            academic_year=academic_year,
            term=term,
            is_active=False,
        )

        # Get the school's timetable structure
        structure = TimetableStructure.objects.get(school=school_class.school)
        time_slots = TimeSlot.objects.filter(school=school_class.school).order_by(
            "day_of_week", "order"
        )

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

        # Get active constraints if requested
        constraints = {}
        if apply_constraints:
            for constraint in TimetableConstraint.objects.filter(
                school=school_class.school, is_active=True
            ):
                constraints[constraint.constraint_type] = constraint

        # Track scheduled lessons for constraint checking
        scheduled_lessons = []

        # First pass - schedule all mandatory breaks
        for time_slot in time_slots:
            if time_slot.is_break:
                scheduled_lessons.append(
                    {
                        "time_slot": time_slot,
                        "is_break": True,
                        "break_name": time_slot.break_name,
                    }
                )

        # Second pass - schedule subjects
        for time_slot in time_slots:
            if time_slot.is_break:
                continue  # Skip break slots

            # Get available subjects (those not yet fully scheduled)
            available_subjects = [
                subj
                for subj in subjects
                if subj.periods_per_week
                > Lesson.objects.filter(timetable=timetable, subject=subj).count()
            ]

            if not available_subjects:
                continue

            # Try to schedule each available subject until one fits
            for subject in available_subjects:
                # Get available teachers for this subject
                available_teachers = subject_teachers.get(subject.id, [])
                if not available_teachers:
                    continue

                # Try each teacher until one fits
                for teacher in available_teachers:
                    # Check if this lesson would violate any constraints
                    if not self._check_constraints(
                        constraints,
                        timetable,
                        subject,
                        teacher,
                        time_slot,
                        scheduled_lessons,
                    ):
                        continue  # Skip if constraints would be violated

                    # Create the lesson
                    lesson = Lesson.objects.create(
                        timetable=timetable,
                        subject=subject,
                        teacher=teacher,
                        time_slot=time_slot,
                    )
                    scheduled_lessons.append(
                        {
                            "lesson": lesson,
                            "time_slot": time_slot,
                            "subject": subject,
                            "teacher": teacher,
                        }
                    )
                    break  # Move to next time slot after successful scheduling

        return timetable

    def _check_constraints(
        self, constraints, timetable, subject, teacher, time_slot, scheduled_lessons
    ):
        """Check if a potential lesson would violate any constraints"""
        school = timetable.school_class.school
        # Retrieve the timetable structure for use in constraints
        structure = TimetableStructure.objects.get(school=school)

        # 1. Check teacher constraints
        if "NO_TEACHER_CLASH" in constraints:
            teacher_clash = Lesson.objects.filter(
                timetable__school_class__school=school,
                time_slot=time_slot,
                teacher=teacher,
            ).exists()
            if teacher_clash:
                return False

        if "NO_TEACHER_SAME_SUBJECT_CLASH" in constraints:
            same_subject_clash = Lesson.objects.filter(
                timetable__school_class__school=school,
                time_slot=time_slot,
                teacher=teacher,
                subject=subject,
            ).exists()
            if same_subject_clash:
                return False

        # 2. Check class constraints
        if "NO_CLASS_CLASH" in constraints:
            class_clash = Lesson.objects.filter(
                timetable=timetable, time_slot=time_slot
            ).exists()
            if class_clash:
                return False

        # 3. Check subject constraints
        if "NO_CORE_AFTER_LUNCH" in constraints and time_slot.is_after_lunch():
            if subject.name in ["Mathematics", "English", "Kiswahili"]:
                return False

        if "NO_DOUBLE_CORE" in constraints:
            if subject.name in ["Mathematics", "English", "Kiswahili"]:
                # Check if previous slot was same core subject
                prev_lesson = Lesson.objects.filter(
                    timetable=timetable, time_slot__order=time_slot.order - 1
                ).first()
                if prev_lesson and prev_lesson.subject.name == subject.name:
                    return False

        if "MATH_NOT_AFTER_SCIENCE" in constraints and subject.name == "Mathematics":
            prev_lesson = Lesson.objects.filter(
                timetable=timetable, time_slot__order=time_slot.order - 1
            ).first()
            if prev_lesson and prev_lesson.subject.name in [
                "Biology",
                "Physics",
                "Chemistry",
                "Science",
            ]:
                return False

        if "MATH_MORNING_ONLY" in constraints and subject.name == "Mathematics":
            if not time_slot.is_morning():
                return False

        if "ENGLISH_KISWAHILI_SEPARATE" in constraints:
            if subject.name in ["English", "Kiswahili"]:
                prev_lesson = Lesson.objects.filter(
                    timetable=timetable, time_slot__order=time_slot.order - 1
                ).first()
                if prev_lesson and prev_lesson.subject.name in ["English", "Kiswahili"]:
                    return False

        # 4. Check subject grouping
        if "SUBJECT_GROUPING" in constraints:
            group_id = constraints["SUBJECT_GROUPING"].parameters.get("subject_group")
            if group_id:
                group = SubjectGroup.objects.filter(id=group_id).first()
                if group and subject in group.subjects.all():
                    # Check if any other subject from this group is already scheduled
                    group_subjects = group.subjects.exclude(id=subject.id)
                    group_lesson = Lesson.objects.filter(
                        timetable=timetable, subject__in=group_subjects
                    ).exists()
                    if group_lesson:
                        return False

        # 5. Check science double period (for 8-4-4 only)
        if "SCIENCE_DOUBLE_PERIOD" in constraints:
            if structure.curriculum == "8-4-4" and subject.name in [
                "Biology",
                "Physics",
                "Chemistry",
            ]:
                # Check if we need to schedule a double period
                science_lessons = Lesson.objects.filter(
                    timetable=timetable, subject=subject
                ).count()
                if science_lessons == 0:  # First science lesson of the week
                    # Check if next time slot is available for double period
                    next_slot = TimeSlot.objects.filter(
                        school=school,
                        day_of_week=time_slot.day_of_week,
                        order=time_slot.order + 1,
                        is_break=False,
                    ).first()
                    if (
                        next_slot
                        and not Lesson.objects.filter(
                            timetable=timetable, time_slot=next_slot
                        ).exists()
                    ):
                        # Schedule double period
                        lesson = Lesson.objects.create(
                            timetable=timetable,
                            subject=subject,
                            teacher=teacher,
                            time_slot=next_slot,
                            is_double_period=True,
                        )
                        scheduled_lessons.append(
                            {
                                "lesson": lesson,
                                "time_slot": next_slot,
                                "subject": subject,
                                "teacher": teacher,
                                "is_double_period": True,
                            }
                        )

        return True  # All constraints passed

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
    # permission_classes = [IsAuthenticated, HasRolePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["school", "constraint_type", "is_hard_constraint", "is_active"]
    search_fields = ["description"]
    required_permission = "manage_timetable_settings"

    # def get_queryset(self):
    #     queryset = super().get_queryset()
    #     user = self.request.user

    #     if user.user_type == "school_admin":
    #         return queryset.filter(school=user.school_admin_profile.school)
    #     elif hasattr(user, "administrator_profile"):
    #         return queryset.filter(school=user.administrator_profile.school)

    #     return queryset.none()

    def get_queryset(self):
        queryset = super().get_queryset()
        school_code = self.request.query_params.get("school")
        school_id = self.request.query_params.get("school_id")

        # Try to get school by code first
        if school_code:
            try:
                return queryset.filter(school__code=school_code)
            except ValueError:
                # Handle case where code is invalid
                return queryset.none()

        # Fall back to school ID if provided
        if school_id:
            return queryset.filter(school_id=school_id)

        # For authenticated users, try to get school from profile
        user = self.request.user
        if hasattr(user, "school_admin_profile") and user.school_admin_profile.school:
            return queryset.filter(school=user.school_admin_profile.school)

        return queryset.none()


class SubjectGroupViewSet(viewsets.ModelViewSet):
    queryset = SubjectGroup.objects.all()
    serializer_class = SubjectGroupSerializer
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
    def assign_to_constraint(self, request, pk=None):
        """Assign this subject group to a timetable constraint"""
        subject_group = self.get_object()
        constraint_id = request.data.get("constraint_id")

        if not constraint_id:
            return Response(
                {"error": "constraint_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            constraint = TimetableConstraint.objects.get(
                id=constraint_id,
                school=subject_group.school,
                constraint_type="SUBJECT_GROUPING",
            )
            constraint.parameters = {"subject_group": subject_group.id}
            constraint.save()

            return Response(
                {"status": f"Subject group assigned to constraint {constraint.id}"},
                status=status.HTTP_200_OK,
            )
        except TimetableConstraint.DoesNotExist:
            return Response(
                {"error": "Constraint not found or not a subject grouping constraint"},
                status=status.HTTP_404_NOT_FOUND,
            )


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
