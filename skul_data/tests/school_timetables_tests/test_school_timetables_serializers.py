# tests/serializers/test_timetable_serializers.py
from django.test import TestCase
from rest_framework.exceptions import ValidationError
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
from skul_data.school_timetables.models.school_timetable import (
    TimeSlot,
    TimetableStructure,
)
from datetime import time


class TimeSlotSerializerTest(TestCase):
    def setUp(self):
        # Clear any existing data first
        TimeSlot.objects.all().delete()
        self.school, _ = create_test_school()

        # Create a unique timeslot for testing
        self.timeslot = TimeSlot.objects.create(
            school=self.school,
            name="Test Period",
            start_time=time(8, 0),  # Now using datetime.time
            end_time=time(8, 40),  # Now using datetime.time
            day_of_week="MON",
            order=1,
            is_active=True,
        )

    def tearDown(self):
        # Clear all test data
        try:
            TimeSlot.objects.all().delete()
        except:
            pass

    def test_serialization(self):
        serializer = TimeSlotSerializer(self.timeslot)
        data = serializer.data
        self.assertEqual(data["name"], self.timeslot.name)
        self.assertEqual(data["day_of_week"], self.timeslot.day_of_week)
        self.assertTrue("start_time" in data)
        self.assertTrue("end_time" in data)

    def test_deserialization(self):
        # Use unique values that don't conflict with existing timeslots
        data = {
            "name": "Unique New Period",
            "start_time": "09:00:00",  # Different from default 8:00
            "end_time": "09:40:00",  # Different from default 8:40
            "day_of_week": "WED",  # Different from setUp's "MON"
            "is_break": False,
            "order": 3,  # Different from setUp's 1
            "is_active": True,
        }

        serializer = TimeSlotSerializer(data=data, context={"request": None})
        self.assertTrue(serializer.is_valid())

        instance = serializer.save(school=self.school)
        self.assertEqual(instance.name, "Unique New Period")


class TimetableStructureSerializerTest(TestCase):
    def setUp(self):
        # Clean up any existing structures first
        TimetableStructure.objects.all().delete()
        TimeSlot.objects.all().delete()

        self.school, _ = create_test_school()
        self.structure = create_test_timetable_structure(self.school)

    def test_serialization(self):
        # Generate timeslots first
        self.structure.generate_time_slots()

        serializer = TimetableStructureSerializer(self.structure)
        data = serializer.data

        self.assertEqual(data["curriculum"], "CBC")
        self.assertEqual(len(data["days_of_week"]), 5)
        self.assertTrue("time_slots" in data)
        self.assertIsInstance(data["time_slots"], list)
        self.assertGreater(len(data["time_slots"]), 0)

    def test_deserialization(self):
        # Delete any existing structure for this school first
        TimetableStructure.objects.filter(school=self.school).delete()

        data = {
            "curriculum": "8-4-4",
            "days_of_week": ["MON", "TUE", "WED"],
            "default_start_time": "08:00:00",
            "default_end_time": "16:00:00",
            "period_duration": 40,
            "break_duration": 30,
            "lunch_duration": 60,
        }

        serializer = TimetableStructureSerializer(
            data=data, context={"request": None, "school": self.school}
        )

        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        self.assertEqual(instance.curriculum, "8-4-4")

    def test_validation_empty_days(self):
        data = {
            "curriculum": "8-4-4",
            "days_of_week": [],
            "default_start_time": "08:00:00",
            "default_end_time": "16:00:00",
            "period_duration": 40,
            "break_duration": 30,
            "lunch_duration": 60,
        }
        serializer = TimetableStructureSerializer(data=data, context={"request": None})
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class TimetableSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.timetable = create_test_timetable(self.school_class)

    def test_serialization(self):
        serializer = TimetableSerializer(self.timetable)
        data = serializer.data
        self.assertEqual(data["academic_year"], "2023")
        self.assertEqual(data["term"], 1)
        self.assertTrue("school_class_details" in data)

    def test_deserialization(self):
        data = {
            "school_class": self.school_class.id,
            "academic_year": "2024",
            "term": 2,
            "is_active": False,
        }
        serializer = TimetableSerializer(data=data, context={"request": None})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        self.assertEqual(instance.academic_year, "2024")


class LessonSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.timetable = create_test_timetable(self.school_class)
        self.teacher = create_test_teacher(self.school)
        self.subject = create_test_subject(self.school)
        self.timeslot = create_test_timeslot(self.school)
        self.lesson = create_test_lesson(
            self.timetable, self.subject, self.teacher, self.timeslot
        )

    def test_serialization(self):
        # Refresh the lesson from database to ensure all relationships are loaded
        self.lesson.refresh_from_db()
        serializer = LessonSerializer(self.lesson)
        data = serializer.data
        self.assertEqual(data["is_double_period"], False)
        self.assertTrue("subject_details" in data)
        self.assertTrue("teacher_details" in data)
        self.assertTrue("time_slot_details" in data)

    def test_deserialization(self):
        from datetime import time  # Import at the top

        # Create unique timeslot
        unique_time = time(9, 0)  # 9:00 AM
        new_timeslot = TimeSlot.objects.create(
            school=self.school,
            name="Unique Test Slot",
            start_time=unique_time,
            end_time=time(9, 40),
            day_of_week="MON",
            order=99,
        )

        data = {
            "timetable": self.timetable.id,
            "subject": self.subject.id,
            "teacher": self.teacher.id,
            "time_slot": new_timeslot.id,
            "is_double_period": True,
            "room": "Lab 1",
            "notes": "Double period for practical",
        }

        serializer = LessonSerializer(data=data, context={"request": None})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        self.assertTrue(instance.is_double_period)


class TimetableConstraintSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.constraint = create_test_constraint(self.school)

    def test_serialization(self):
        serializer = TimetableConstraintSerializer(self.constraint)
        data = serializer.data
        self.assertEqual(data["constraint_type"], "NO_TEACHER_CLASH")
        self.assertTrue(data["is_hard_constraint"])

    def test_deserialization(self):
        data = {
            "school": self.school.id,
            "constraint_type": "SCIENCE_DOUBLE",
            "is_hard_constraint": True,
            "parameters": {"subject_id": 1},
            "description": "Science needs double period",
            "is_active": True,
        }
        serializer = TimetableConstraintSerializer(data=data, context={"request": None})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        self.assertEqual(instance.constraint_type, "SCIENCE_DOUBLE")


class SubjectGroupSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.subject1 = create_test_subject(self.school, name="Math")
        self.subject2 = create_test_subject(self.school, name="Science")
        self.group = create_test_subject_group(
            self.school, subjects=[self.subject1, self.subject2]
        )

    def test_serialization(self):
        serializer = SubjectGroupSerializer(self.group)
        data = serializer.data
        self.assertEqual(data["name"], "Test Group")
        self.assertEqual(len(data["subjects"]), 2)

    def test_deserialization(self):
        data = {
            "school": self.school.id,
            "name": "Science Group",
            "subject_ids": [self.subject1.id, self.subject2.id],
            "description": "Group for science subjects",
        }
        serializer = SubjectGroupSerializer(data=data, context={"request": None})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        self.assertEqual(instance.subjects.count(), 2)


class TeacherAvailabilitySerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.availability = create_test_teacher_availability(self.teacher)

    def test_serialization(self):
        # Refresh from database to ensure all fields are properly loaded
        self.availability.refresh_from_db()
        serializer = TeacherAvailabilitySerializer(self.availability)
        data = serializer.data
        self.assertEqual(data["day_of_week"], "MON")
        self.assertTrue(data["is_available"])
        self.assertTrue("teacher_details" in data)

    def test_deserialization(self):
        data = {
            "teacher": self.teacher.id,
            "day_of_week": "TUE",
            "is_available": False,
            "available_from": "08:00:00",
            "available_to": "16:00:00",
            "reason": "Weekly meeting",
        }
        serializer = TeacherAvailabilitySerializer(data=data, context={"request": None})

        # Print validation errors if not valid for debugging
        if not serializer.is_valid():
            print(
                "Teacher availability serializer validation errors:", serializer.errors
            )

        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        self.assertEqual(instance.day_of_week, "TUE")


class TimetableGenerateSerializerTest(TestCase):
    def test_validation(self):
        # Valid data
        data = {
            "school_class_ids": [1, 2, 3],
            "academic_year": "2023",
            "term": 1,
            "regenerate_existing": False,
            "apply_constraints": True,
        }
        serializer = TimetableGenerateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid data - empty class IDs
        data = {
            "school_class_ids": [],
            "academic_year": "2023",
            "term": 1,
        }
        serializer = TimetableGenerateSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class TimetableCloneSerializerTest(TestCase):
    def test_validation(self):
        # Valid data
        data = {
            "source_academic_year": "2023",
            "source_term": 1,
            "target_academic_year": "2024",
            "target_term": 1,
            "school_class_ids": [1, 2, 3],
        }
        serializer = TimetableCloneSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid data - empty class IDs
        data = {
            "source_academic_year": "2023",
            "source_term": 1,
            "target_academic_year": "2024",
            "target_term": 1,
            "school_class_ids": [],
        }
        serializer = TimetableCloneSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


# python manage.py test skul_data.tests.school_timetables_tests.test_school_timetables_serializers
