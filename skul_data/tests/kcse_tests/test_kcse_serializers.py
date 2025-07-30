from django.test import TestCase
from rest_framework.exceptions import ValidationError
from io import BytesIO
import pandas as pd
from skul_data.tests.kcse_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_subject,
    create_test_kcse_result,
    create_test_kcse_subject_result,
    create_test_class,
    create_test_parent,
    create_test_teacher,
)
from skul_data.kcse.serializers.kcse import (
    KCSEResultSerializer,
    KCSESubjectResultSerializer,
    KCSEResultUploadSerializer,
    KCSEStudentTemplateSerializer,
)
from django.core.files.uploadedfile import SimpleUploadedFile
from skul_data.students.models.student import Student
import random
from django.utils import timezone
from datetime import timedelta
from skul_data.students.models.student import StudentStatus


class KCSEResultSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)
        self.kcse_result = create_test_kcse_result(self.student)
        self.subject = create_test_subject(self.school)
        create_test_kcse_subject_result(self.kcse_result, self.subject)

    def test_serializer_data(self):
        serializer = KCSEResultSerializer(instance=self.kcse_result)
        data = serializer.data
        self.assertEqual(data["year"], self.kcse_result.year)
        self.assertEqual(data["mean_grade"], self.kcse_result.mean_grade)
        self.assertEqual(
            float(data["mean_points"]), float(self.kcse_result.mean_points)
        )
        self.assertEqual(len(data["subject_results"]), 1)


class KCSESubjectResultSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)
        self.kcse_result = create_test_kcse_result(self.student)
        self.subject = create_test_subject(self.school)
        self.subject_result = create_test_kcse_subject_result(
            self.kcse_result, self.subject
        )

    def test_serializer_data(self):
        serializer = KCSESubjectResultSerializer(instance=self.subject_result)
        data = serializer.data
        self.assertEqual(data["grade"], self.subject_result.grade)
        self.assertEqual(data["points"], self.subject_result.points)
        self.assertEqual(data["subject"]["id"], self.subject.id)


class KCSEResultUploadSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school, status="GRADUATED")
        self.subject = create_test_subject(self.school, code="101")

    def create_test_csv(self):
        data = {
            "Index Number": ["123456"],
            "Admission Number": [self.student.admission_number],
            "Name": [self.student.full_name],
            "ENG": ["A"],
            "KIS": ["B+"],
            "MAT": ["A-"],
            "Mean Grade": ["A-"],
            "Total Points": [80],
        }
        df = pd.DataFrame(data)
        output = BytesIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return SimpleUploadedFile(
            "test_results.csv",
            output.getvalue(),  # Remove .encode('utf-8') since it's already bytes
            content_type="text/csv",
        )

    def test_upload_validation(self):
        csv_file = self.create_test_csv()
        data = {
            "file": csv_file,
            "year": 2023,
            "publish": False,
        }
        serializer = KCSEResultUploadSerializer(
            data=data, context={"request": type("obj", (object,), {"user": self.admin})}
        )
        self.assertTrue(
            serializer.is_valid(), msg=serializer.errors
        )  # Add msg parameter

    def test_invalid_year(self):
        csv_file = self.create_test_csv()
        data = {
            "file": csv_file,
            "year": 1988,
            "publish": False,
        }
        serializer = KCSEResultUploadSerializer(
            data=data, context={"request": type("obj", (object,), {"user": self.admin})}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_missing_columns(self):
        data = {
            "Index Number": ["123456"],
            "Admission Number": [self.student.admission_number],
        }
        df = pd.DataFrame(data)
        output = BytesIO()
        df.to_csv(output, index=False)
        output.seek(0)

        data = {
            "file": output,
            "year": 2023,
            "publish": False,
        }
        serializer = KCSEResultUploadSerializer(
            data=data, context={"request": type("obj", (object,), {"user": self.admin})}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class KCSEStudentTemplateSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()

        # Instead of trying to set school directly on user, update the SchoolAdmin profile
        # This assumes create_test_school() already creates a SchoolAdmin profile
        self.admin.school_admin_profile.school = self.school
        self.admin.school_admin_profile.save()

        self.class_ = create_test_class(self.school, name="Form 4 East")

        # Create student
        self.student = Student.objects.create(
            first_name="Test",
            last_name="Student",
            date_of_birth=timezone.now().date() - timedelta(days=365 * 15),
            admission_date=timezone.now().date(),
            gender="M",
            school=self.school,
            parent=create_test_parent(self.school),
            teacher=create_test_teacher(self.school),
            admission_number=f"ADM-{timezone.now().year}-4456",
            student_class=self.class_,
            status=StudentStatus.GRADUATED,
        )

    def test_template_creation(self):
        # Verify the student exists with correct attributes
        db_student = Student.objects.get(admission_number=self.student.admission_number)
        self.assertEqual(db_student.status, StudentStatus.GRADUATED)
        self.assertEqual(db_student.school, self.school)
        self.assertEqual(db_student.student_class.name, "Form 4 East")

        print(f"\nAdmin user school: {self.admin.school}")  # Should not be None
        print(f"Created school ID: {self.school.id}")

        data = {
            "year": 2023,
            "class_name": "Form 4 East",  # Must match exactly
        }

        serializer = KCSEStudentTemplateSerializer(
            data=data, context={"request": type("obj", (object,), {"user": self.admin})}
        )

        self.assertTrue(serializer.is_valid(), msg=serializer.errors)

        result = serializer.save()
        csv_data = result["csv_data"]

        # Verify CSV contains expected data
        self.assertIn(self.student.admission_number, csv_data)
        self.assertIn(self.student.full_name, csv_data)
        self.assertIn("Form 4 East", csv_data)


# python manage.py test skul_data.tests.kcse_tests.test_kcse_serializers
