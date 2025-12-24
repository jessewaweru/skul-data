from urllib import request
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
from rest_framework import serializers
from skul_data.students.models.student import Subject


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
        if getattr(self, "swagger_fake_view", False):
            return TimeSlot.objects.none()
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
        if getattr(self, "swagger_fake_view", False):
            return TimetableStructure.objects.none()
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
        if getattr(self, "swagger_fake_view", False):
            return Timetable.objects.none()
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
        subject_assignments = data.get("subject_assignments", [])  # GET ASSIGNMENTS

        # Log what we received
        print(f"\n{'='*60}")
        print(f"GENERATE TIMETABLE REQUEST")
        print(f"{'='*60}")
        print(f"Classes: {class_ids}")
        print(f"Subject assignments received: {len(subject_assignments)}")

        if subject_assignments:
            print("Subjects:")
            for assign in subject_assignments:
                print(
                    f"  - {assign.get('subject_name')} (ID: {assign.get('subject_id')}) "
                    f"Teacher: {assign.get('teacher_id')}, Periods: {assign.get('required_periods')}"
                )

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

        if existing_timetables.exists():
            if not regenerate:
                return Response(
                    {
                        "error": "Timetables already exist for these classes in this term",
                        "detail": "Set regenerate_existing to true to overwrite",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            print(f"Deleting {existing_timetables.count()} existing timetables")
            existing_timetables.delete()

        # Generate timetables
        timetables = []
        errors = []

        for school_class in classes:
            try:
                timetable = self._generate_timetable(
                    school_class,
                    academic_year,
                    term,
                    apply_constraints,
                    subject_assignments,  # PASS ASSIGNMENTS
                )
                timetables.append(timetable)

            except Exception as e:
                error_msg = (
                    f"Error generating timetable for {school_class.name}: {str(e)}"
                )
                errors.append(error_msg)
                print(error_msg)
                import traceback

                traceback.print_exc()

        if not timetables:
            return Response(
                {"error": "Failed to generate any timetables", "details": errors},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        log_action(
            user=request.user,
            action=f"Generated timetables for {len(timetables)} classes",
            category=ActionCategory.CREATE,
            metadata={
                "class_ids": class_ids,
                "academic_year": academic_year,
                "term": term,
                "apply_constraints": apply_constraints,
                "errors": errors,
            },
        )

        # Return detailed response
        response_data = {
            "id": timetables[0].id if timetables else None,
            "academic_year": academic_year,
            "term": term,
            "is_active": False,
            "classes": [
                {
                    "id": tt.school_class.id,
                    "name": tt.school_class.name,
                }
                for tt in timetables
            ],
            "lessons": [],
            "time_slots": [],
            "errors": errors,
        }

        # Add lessons from all timetables
        for timetable in timetables:
            lessons_data = LessonSerializer(timetable.lessons.all(), many=True).data
            for lesson in lessons_data:
                lesson["class_id"] = timetable.school_class.id
            response_data["lessons"].extend(lessons_data)

        # Add ALL time slots (sorted properly)
        if timetables:
            all_time_slots = TimeSlot.objects.filter(
                school=timetables[0].school_class.school
            ).order_by("day_order", "start_time", "order")

            response_data["time_slots"] = TimeSlotSerializer(
                all_time_slots, many=True
            ).data

            print(f"\nResponse includes {len(response_data['time_slots'])} time slots")
            print(f"Response includes {len(response_data['lessons'])} lessons")

        return Response(response_data, status=status.HTTP_201_CREATED)

    def _generate_timetable(
        self,
        school_class,
        academic_year,
        term,
        apply_constraints,
        subject_assignments=None,
    ):
        """Generate timetable with proper subject assignment handling"""
        from collections import defaultdict
        import random

        print(f"\n{'='*60}")
        print(f"GENERATING TIMETABLE FOR {school_class.name}")
        print(f"{'='*60}")

        # Create timetable
        timetable = Timetable.objects.create(
            school_class=school_class,
            academic_year=academic_year,
            term=term,
            is_active=False,
        )

        # Get structure and ALL time slots (non-break)
        try:
            structure = TimetableStructure.objects.get(school=school_class.school)
            all_time_slots = list(
                TimeSlot.objects.filter(
                    school=school_class.school, is_break=False, is_active=True
                ).order_by("day_order", "start_time", "order")
            )

            if not all_time_slots:
                raise serializers.ValidationError("No time slots available")

            print(f"Total available time slots: {len(all_time_slots)}")

        except TimetableStructure.DoesNotExist:
            raise serializers.ValidationError("Timetable structure not found")

        # Build subject-teacher mapping from assignments
        subject_teacher_map = {}
        subject_periods_needed = {}

        if subject_assignments and len(subject_assignments) > 0:
            print(
                f"\nUsing {len(subject_assignments)} subject assignments from request"
            )

            for assignment in subject_assignments:
                subject_id = assignment.get("subject_id")
                teacher_id = assignment.get("teacher_id")
                periods = assignment.get("required_periods", 5)

                if subject_id and teacher_id:
                    try:
                        subject = Subject.objects.get(id=subject_id)
                        teacher = Teacher.objects.get(id=teacher_id)

                        subject_teacher_map[subject_id] = teacher
                        subject_periods_needed[subject_id] = periods

                        print(
                            f"  ✓ {subject.name}: {teacher.user.get_full_name()} ({periods} periods)"
                        )
                    except (Subject.DoesNotExist, Teacher.DoesNotExist) as e:
                        print(f"  ✗ Invalid assignment: {e}")
                        continue
        else:
            # Fallback: Use class subjects
            print("\nNo subject assignments provided, using class subjects")
            subjects = list(school_class.subjects.all())

            if not subjects:
                raise serializers.ValidationError(
                    f"No subjects assigned to {school_class.name}"
                )

            for subject in subjects:
                teachers = list(
                    Teacher.objects.filter(
                        subjects_taught=subject, school=school_class.school
                    )
                )

                if teachers:
                    subject_teacher_map[subject.id] = random.choice(teachers)
                    subject_periods_needed[subject.id] = (
                        getattr(subject, "periods_per_week", 5) or 5
                    )
                    print(
                        f"  ✓ {subject.name}: Auto-assigned teacher ({subject_periods_needed[subject.id]} periods)"
                    )

        if not subject_teacher_map:
            raise serializers.ValidationError("No valid subject-teacher assignments")

        print(f"\nTotal subjects to schedule: {len(subject_teacher_map)}")
        print(f"Total periods needed: {sum(subject_periods_needed.values())}")
        print(f"Available slots: {len(all_time_slots)}")

        # Group slots by day
        slots_by_day = defaultdict(list)
        for slot in all_time_slots:
            slots_by_day[slot.day_of_week].append(slot)

        days = ["MON", "TUE", "WED", "THU", "FRI"]

        print(f"\nSlot distribution:")
        for day in days:
            print(f"  {day}: {len(slots_by_day[day])} slots")

        # Get constraints
        active_constraints = []
        if apply_constraints:
            active_constraints = list(
                TimetableConstraint.objects.filter(
                    school=school_class.school,
                    is_active=True,
                    constraint_type__in=["NO_TEACHER_CLASH", "NO_CLASS_CLASH"],
                )
            )
            print(f"\nApplying {len(active_constraints)} constraints")

        # Create subject pool with proper distribution
        subject_pool = []
        for subject_id, periods in subject_periods_needed.items():
            for _ in range(periods):
                subject_pool.append(subject_id)

        random.shuffle(subject_pool)
        print(f"\nSubject pool size: {len(subject_pool)} periods")

        # Track usage
        subject_periods_scheduled = defaultdict(int)
        daily_subject_count = {day: defaultdict(int) for day in days}
        teacher_slots = defaultdict(set)
        scheduled_lessons = []

        print(f"\n{'='*60}")
        print("SCHEDULING LESSONS")
        print(f"{'='*60}")

        # Schedule lessons day by day
        for day in days:
            day_slots = slots_by_day[day]
            if not day_slots:
                continue

            print(f"\n{day} ({len(day_slots)} slots):")

            for slot in day_slots:
                if not subject_pool:
                    print(f"  ⚠ Subject pool exhausted at {slot.start_time}")
                    break

                # Find best subject for this slot (least used today)
                best_subject_id = None
                best_subject_idx = None
                min_usage = float("inf")

                for idx, subj_id in enumerate(subject_pool):
                    usage = daily_subject_count[day][subj_id]
                    if usage < min_usage:
                        min_usage = usage
                        best_subject_id = subj_id
                        best_subject_idx = idx

                if best_subject_id is None:
                    continue

                # Remove from pool
                subject_pool.pop(best_subject_idx)

                # Get subject and teacher
                try:
                    subject = Subject.objects.get(id=best_subject_id)
                    teacher = subject_teacher_map[best_subject_id]
                except Subject.DoesNotExist:
                    print(f"  ✗ Subject {best_subject_id} not found")
                    continue

                # Check constraints
                if active_constraints:
                    # Teacher clash
                    if slot.id in teacher_slots[teacher.id]:
                        print(f"  ✗ {subject.name}: Teacher busy")
                        continue

                    # Slot already used
                    if Lesson.objects.filter(
                        timetable=timetable, time_slot=slot
                    ).exists():
                        print(f"  ✗ Slot already used at {slot.start_time}")
                        continue

                # Create lesson
                try:
                    lesson = Lesson.objects.create(
                        timetable=timetable,
                        subject=subject,
                        teacher=teacher,
                        time_slot=slot,
                        is_double_period=False,
                    )

                    scheduled_lessons.append(lesson)
                    subject_periods_scheduled[best_subject_id] += 1
                    daily_subject_count[day][best_subject_id] += 1
                    teacher_slots[teacher.id].add(slot.id)

                    print(
                        f"  ✓ {slot.start_time}: {subject.name} - {teacher.user.get_full_name()}"
                    )

                except Exception as e:
                    print(f"  ✗ Error at {slot.start_time}: {e}")

        # Summary
        print(f"\n{'='*60}")
        print("GENERATION SUMMARY")
        print(f"{'='*60}")

        for subject_id, needed in subject_periods_needed.items():
            scheduled = subject_periods_scheduled[subject_id]
            subject = Subject.objects.get(id=subject_id)
            status = "✓" if scheduled >= needed else "✗"
            print(f"{status} {subject.name}: {scheduled}/{needed} periods")

        print(f"\nTotal lessons: {len(scheduled_lessons)}")
        print(
            f"Fill rate: {len(scheduled_lessons)}/{len(all_time_slots)} ({len(scheduled_lessons)/len(all_time_slots)*100:.1f}%)"
        )

        return timetable

    def _check_all_constraints(
        self,
        constraints,
        timetable,
        subject,
        teacher,
        time_slot,
        scheduled_lessons,
        structure,
    ):
        """Check all active constraints for a potential lesson"""

        for constraint in constraints:
            constraint_type = constraint.constraint_type

            if constraint_type == "NO_TEACHER_CLASH":
                clash = Lesson.objects.filter(
                    timetable__school_class__school=timetable.school_class.school,
                    time_slot=time_slot,
                    teacher=teacher,
                ).exists()
                if clash:
                    return False

            elif constraint_type == "NO_CLASS_CLASH":
                clash = Lesson.objects.filter(
                    timetable=timetable, time_slot=time_slot
                ).exists()
                if clash:
                    return False

            elif constraint_type == "NO_CORE_AFTER_LUNCH":
                if time_slot.is_after_lunch() and subject.name in [
                    "Mathematics",
                    "English",
                    "Kiswahili",
                ]:
                    return False

            elif constraint_type == "MATH_MORNING_ONLY":
                if subject.name == "Mathematics" and not time_slot.is_morning():
                    return False

            elif constraint_type == "NO_DOUBLE_CORE":
                if subject.name in ["Mathematics", "English", "Kiswahili"]:
                    prev_lessons = Lesson.objects.filter(
                        timetable=timetable,
                        time_slot__order=time_slot.order - 1,
                        time_slot__day_of_week=time_slot.day_of_week,
                        subject=subject,
                    )
                    if prev_lessons.exists():
                        return False

            elif constraint_type == "MATH_NOT_AFTER_SCIENCE":
                if subject.name == "Mathematics":
                    prev_lessons = Lesson.objects.filter(
                        timetable=timetable,
                        time_slot__order=time_slot.order - 1,
                        time_slot__day_of_week=time_slot.day_of_week,
                    )
                    for prev_lesson in prev_lessons:
                        if prev_lesson.subject.name in [
                            "Biology",
                            "Physics",
                            "Chemistry",
                            "Science",
                        ]:
                            return False

            elif constraint_type == "ENGLISH_KISWAHILI_SEPARATE":
                if subject.name in ["English", "Kiswahili"]:
                    prev_lessons = Lesson.objects.filter(
                        timetable=timetable,
                        time_slot__order=time_slot.order - 1,
                        time_slot__day_of_week=time_slot.day_of_week,
                    )
                    for prev_lesson in prev_lessons:
                        if prev_lesson.subject.name in ["English", "Kiswahili"]:
                            return False

        return True

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

        source_timetables = Timetable.objects.filter(
            school_class__id__in=class_ids, academic_year=source_year, term=source_term
        )

        if source_timetables.count() != len(class_ids):
            return Response(
                {"error": "Not all classes have source timetables"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_targets = Timetable.objects.filter(
            school_class__id__in=class_ids, academic_year=target_year, term=target_term
        )
        if existing_targets.exists():
            return Response(
                {"error": "Target timetables already exist for some classes"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cloned_timetables = []
        for source in source_timetables:
            new_timetable = Timetable.objects.create(
                school_class=source.school_class,
                academic_year=target_year,
                term=target_term,
                is_active=False,
            )

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
            action=f"Cloned {len(cloned_timetables)} timetables",
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
        if getattr(self, "swagger_fake_view", False):
            return Lesson.objects.none()
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
        if getattr(self, "swagger_fake_view", False):
            return SubjectGroup.objects.none()
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
        if getattr(self, "swagger_fake_view", False):
            return TeacherAvailability.objects.none()
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
