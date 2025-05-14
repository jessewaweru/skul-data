# students/tests/test_serializers.py
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from skul_data.students.serializers.student import (
    StudentCreateSerializer,
    BulkAttendanceSerializer,
    StudentSerializer,
    StudentPromoteSerializer,
    StudentTransferSerializer,
    StudentAttendanceSerializer,
)
from rest_framework.exceptions import ValidationError
from skul_data.tests.students_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_parent,
    create_test_class,
    create_test_student,
)


class StudentCreateSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.parent = create_test_parent(self.school)
        self.school_class = create_test_class(self.school)

    def test_valid_student_creation(self):
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "date_of_birth": (
                timezone.now().date() - timedelta(days=365 * 12)
            ).isoformat(),
            "gender": "F",
            "student_class": self.school_class.id,
            "parent": self.parent.id,
        }
        serializer = StudentCreateSerializer(
            data=data,
            context={"request": type("obj", (object,), {"user": self.admin})()},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        student = serializer.save()
        self.assertEqual(student.full_name, "Jane Doe")
        self.assertTrue(student.admission_number.startswith(self.school.code))

    def test_invalid_status_on_create(self):
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "date_of_birth": (
                timezone.now().date() - timedelta(days=365 * 12)
            ).isoformat(),
            "gender": "F",
            "status": "GRADUATED",  # This should cause validation error
            "student_class": self.school_class.id,
            "parent": self.parent.id,
        }
        serializer = StudentCreateSerializer(
            data=data,
            context={"request": type("obj", (object,), {"user": self.admin})()},
        )

        # Add debugging to see what's happening
        is_valid = serializer.is_valid()
        print(f"Is valid: {is_valid}")
        print(f"Serializer errors: {serializer.errors}")
        print(f"Validated data: {serializer.validated_data if is_valid else 'N/A'}")

        # Should be invalid because we're trying to set status
        self.assertFalse(is_valid)

        # Should have a status error
        self.assertIn("status", serializer.errors)
        self.assertEqual(
            serializer.errors["status"][0],
            "Cannot set status directly on creation. New students are always ACTIVE.",
        )


class StudentSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)

    def test_student_serialization(self):
        serializer = StudentSerializer(self.student)
        self.assertEqual(serializer.data["full_name"], "John Doe")
        self.assertEqual(serializer.data["age"], 10)

    def test_student_update_validation(self):
        data = {
            "first_name": "Johnny",
            "status": "GRADUATED",  # Should not be allowed to update status directly
        }
        serializer = StudentSerializer(instance=self.student, data=data, partial=True)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class StudentPromoteSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()

        # Create classes first
        self.old_class = create_test_class(
            self.school, name="Form 1", academic_year="2023"
        )
        self.new_class = create_test_class(
            self.school, name="Form 2", academic_year="2023"
        )

        # Pass the class explicitly to student creation
        self.student = create_test_student(
            self.school, student_class=self.old_class  # Explicitly set the class
        )

    def test_valid_promotion(self):
        data = {"new_class_id": self.new_class.id}
        serializer = StudentPromoteSerializer(
            data=data, context={"student": self.student}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_same_class_promotion(self):
        data = {"new_class_id": self.old_class.id}
        serializer = StudentPromoteSerializer(
            data=data, context={"student": self.student}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class StudentTransferSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.new_school, _ = create_test_school(name="New School")
        self.student = create_test_student(self.school)

    def test_valid_transfer(self):
        data = {
            "new_school_id": self.new_school.id,
            "transfer_date": timezone.now().date().isoformat(),
            "reason": "Family relocation",
        }
        serializer = StudentTransferSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class StudentAttendanceSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)

    def test_valid_attendance(self):
        data = {
            "student": self.student.id,
            "date": timezone.now().date().isoformat(),
            "status": "PRESENT",
        }
        serializer = StudentAttendanceSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_future_date(self):
        data = {
            "student": self.student.id,
            "date": (timezone.now().date() + timedelta(days=1)).isoformat(),
            "status": "PRESENT",
        }
        serializer = StudentAttendanceSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class BulkAttendanceSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)

    def test_valid_bulk_attendance(self):
        data = {
            "date": timezone.now().date().isoformat(),
            "student_statuses": [{"student_id": self.student.id, "status": "PRESENT"}],
        }
        serializer = BulkAttendanceSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_bulk_attendance(self):
        data = {
            "date": timezone.now().date().isoformat(),
            "student_statuses": [{"status": "PRESENT"}],  # Missing student_id
        }
        serializer = BulkAttendanceSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


# python manage.py test skul_data.tests.students_tests.test_students_serializers
