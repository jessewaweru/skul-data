from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import time
from skul_data.tests.school_timetables_tests.test_helpers import (
    create_test_timeslot,
    create_test_timetable_structure,
    create_test_timetable,
    create_test_lesson,
    create_test_constraint,
    create_test_subject_group,
    create_test_teacher_availability,
    create_test_school,
    create_test_class,
    create_test_teacher,
    create_test_subject,
)
from skul_data.school_timetables.models.school_timetable import TimeSlot
from skul_data.school_timetables.models.school_timetable import Timetable


class TimeSlotModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()

    def test_create_timeslot(self):
        timeslot = create_test_timeslot(self.school)
        self.assertEqual(timeslot.school, self.school)
        self.assertTrue(timeslot.is_active)
        self.assertEqual(str(timeslot), f"{timeslot.name} (08:00-08:40)")

    def test_break_timeslot_validation(self):
        with self.assertRaises(ValidationError):
            timeslot = create_test_timeslot(self.school, is_break=True, break_name=None)
            timeslot.full_clean()

    def test_time_validation(self):
        with self.assertRaises(ValidationError):
            timeslot = create_test_timeslot(
                self.school, start_time=time(9, 0), end_time=time(8, 0)
            )
            timeslot.full_clean()

    def test_unique_together_constraint(self):
        create_test_timeslot(
            self.school,
            name="Period 1",
            start_time=time(8, 0),
            end_time=time(8, 40),
            day_of_week="MON",
        )
        with self.assertRaises(Exception):
            create_test_timeslot(
                self.school,
                name="Period 1",
                start_time=time(8, 0),
                end_time=time(8, 40),
                day_of_week="MON",
            )


class TimetableStructureModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()

    def test_create_structure(self):
        structure = create_test_timetable_structure(self.school)
        self.assertEqual(structure.school, self.school)
        self.assertEqual(structure.curriculum, "CBC")
        self.assertEqual(len(structure.days_of_week), 5)
        self.assertEqual(str(structure), f"Timetable Structure for {self.school.name}")

    def test_generate_time_slots(self):
        structure = create_test_timetable_structure(self.school)
        structure.generate_time_slots()

        # Should create time slots for each day
        time_slots = TimeSlot.objects.filter(school=self.school)
        self.assertGreater(time_slots.count(), 0)

        # Check ordering
        first_slot = time_slots.first()
        self.assertEqual(first_slot.order, 1)
        self.assertEqual(first_slot.day_of_week, "MON")


class TimetableModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)

    def test_create_timetable(self):
        timetable = create_test_timetable(self.school_class)
        self.assertEqual(timetable.school_class, self.school_class)
        self.assertEqual(timetable.academic_year, "2023")
        self.assertEqual(timetable.term, 1)
        self.assertFalse(timetable.is_active)
        self.assertEqual(
            str(timetable),
            f"Timetable for {self.school_class} (2023 Term 1)",
        )

    def test_unique_together_constraint(self):
        create_test_timetable(self.school_class)
        with self.assertRaises(Exception):
            create_test_timetable(self.school_class)

    def test_active_timetable_validation(self):
        # Create an active timetable
        active_timetable = create_test_timetable(self.school_class, is_active=True)

        # Try to create another active timetable with different year/term
        with self.assertRaises(ValidationError):
            another_timetable = Timetable(
                school_class=self.school_class,
                academic_year="2023",  # Same year
                term=1,  # Same term
                is_active=True,
            )
            another_timetable.full_clean()  # This should raise ValidationError


class LessonModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.timetable = create_test_timetable(self.school_class)
        self.teacher = create_test_teacher(self.school)
        self.subject = create_test_subject(self.school)
        self.timeslot = create_test_timeslot(self.school)

    def test_create_lesson(self):
        lesson = create_test_lesson(
            self.timetable, self.subject, self.teacher, self.timeslot
        )
        self.assertEqual(lesson.timetable, self.timetable)
        self.assertEqual(lesson.subject, self.subject)
        self.assertEqual(lesson.teacher, self.teacher)
        self.assertEqual(lesson.time_slot, self.timeslot)
        self.assertFalse(lesson.is_double_period)
        self.assertEqual(
            str(lesson),
            f"{self.subject.name} with {self.teacher} at {self.timeslot}",
        )

    def test_unique_together_constraint(self):
        create_test_lesson(self.timetable, self.subject, self.teacher, self.timeslot)
        with self.assertRaises(Exception):
            create_test_lesson(
                self.timetable, self.subject, self.teacher, self.timeslot
            )


class TimetableConstraintModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()

    def test_create_constraint(self):
        constraint = create_test_constraint(self.school)
        self.assertEqual(constraint.school, self.school)
        self.assertEqual(constraint.constraint_type, "NO_TEACHER_CLASH")
        self.assertTrue(constraint.is_hard_constraint)
        self.assertEqual(
            str(constraint),
            "No teacher double booking (Hard)",
        )

    def test_constraint_validation(self):
        # Test SUBJECT_PAIRING validation
        with self.assertRaises(ValidationError):
            constraint = create_test_constraint(
                self.school,
                constraint_type="SUBJECT_PAIRING",
                parameters={},  # Missing subjects
            )
            constraint.full_clean()

        # Test MAX_PERIODS_PER_DAY validation
        with self.assertRaises(ValidationError):
            constraint = create_test_constraint(
                self.school,
                constraint_type="MAX_PERIODS_PER_DAY",
                parameters={},  # Missing max_periods
            )
            constraint.full_clean()


class SubjectGroupModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.subject1 = create_test_subject(self.school, name="Math")
        self.subject2 = create_test_subject(self.school, name="Science")

    def test_create_subject_group(self):
        group = create_test_subject_group(self.school)
        self.assertEqual(group.school, self.school)
        self.assertEqual(group.name, "Test Group")
        self.assertEqual(
            str(group),
            f"Test Group ({self.school.name})",
        )

    def test_unique_together_constraint(self):
        create_test_subject_group(self.school, name="Test Group")
        with self.assertRaises(Exception):
            create_test_subject_group(self.school, name="Test Group")

    def test_subject_relationship(self):
        group = create_test_subject_group(
            self.school, subjects=[self.subject1, self.subject2]
        )
        self.assertEqual(group.subjects.count(), 2)


class TeacherAvailabilityModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.teacher = create_test_teacher(self.school)

    def test_create_availability(self):
        availability = create_test_teacher_availability(self.teacher)
        self.assertEqual(availability.teacher, self.teacher)
        self.assertEqual(availability.day_of_week, "MON")
        self.assertTrue(availability.is_available)
        self.assertEqual(
            str(availability),
            f"{self.teacher} - Monday (Available)",
        )

    def test_unique_together_constraint(self):
        create_test_teacher_availability(self.teacher, day_of_week="MON")
        with self.assertRaises(Exception):
            create_test_teacher_availability(self.teacher, day_of_week="MON")

    def test_time_validation(self):
        with self.assertRaises(ValidationError):
            availability = create_test_teacher_availability(
                self.teacher,
                available_from=time(16, 0),
                available_to=time(8, 0),
                is_available=True,
            )
            availability.full_clean()


# python manage.py test skul_data.tests.school_timetables_tests.test_school_timetables_models
