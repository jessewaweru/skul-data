from django.test import TestCase
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from skul_data.schools.models.schoolclass import (
    SchoolClass,
    ClassTimetable,
    ClassDocument,
    ClassAttendance,
)
from skul_data.schools.models.schoolstream import SchoolStream
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.students.models.student import Student, Subject
from skul_data.schools.models.school import School


class SchoolClassModelTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School", motto="Test Motto")
        self.teacher = Teacher.objects.create(
            user=User.objects.create_user(
                email="teacher@test.com", password="testpass"
            ),
            school=self.school,
        )
        self.stream = SchoolStream.objects.create(school=self.school, name="West")
        self.subject = Subject.objects.create(name="Math", school=self.school)
        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            admission_number="123",
            school=self.school,
        )

        self.class_data = {
            "name": "Grade 1 West",
            "grade_level": "Grade 1",
            "level": "PRIMARY",
            "school": self.school,
            "academic_year": "2023-2024",
            "room_number": "101",
            "capacity": 30,
        }

    def test_create_school_class(self):
        school_class = SchoolClass.objects.create(**self.class_data)
        self.assertEqual(school_class.name, "Grade 1 West")
        self.assertEqual(school_class.student_count, 0)
        self.assertIsNone(school_class.average_performance)

    def test_unique_constraint(self):
        SchoolClass.objects.create(**self.class_data)
        with self.assertRaises(ValidationError):
            SchoolClass.objects.create(**self.class_data)

    def test_student_count_property(self):
        school_class = SchoolClass.objects.create(**self.class_data)
        school_class.students.add(self.student)
        self.assertEqual(school_class.student_count, 1)

    def test_promote_class(self):
        school_class = SchoolClass.objects.create(**self.class_data)
        school_class.subjects.add(self.subject)

        new_class = school_class.promote_class("2024-2025")
        self.assertEqual(new_class.academic_year, "2024-2025")
        self.assertEqual(new_class.subjects.count(), 1)
        self.assertEqual(new_class.name, school_class.name)

    def test_promote_inactive_class_fails(self):
        school_class = SchoolClass.objects.create(**self.class_data, is_active=False)
        with self.assertRaises(ValueError):
            school_class.promote_class("2024-2025")


class ClassTimetableModelTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

    def test_create_timetable(self):
        test_file = SimpleUploadedFile(
            "timetable.pdf", b"file_content", content_type="application/pdf"
        )
        timetable = ClassTimetable.objects.create(
            school_class=self.school_class, file=test_file, description="Test Timetable"
        )
        self.assertEqual(timetable.school_class, self.school_class)
        self.assertTrue(os.path.exists(timetable.file.path))

    def tearDown(self):
        for timetable in ClassTimetable.objects.all():
            if os.path.exists(timetable.file.path):
                os.remove(timetable.file.path)


class ClassDocumentModelTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.user = User.objects.create_user(email="test@test.com", password="testpass")
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

    def test_create_document(self):
        test_file = SimpleUploadedFile(
            "document.pdf", b"file_content", content_type="application/pdf"
        )
        document = ClassDocument.objects.create(
            school_class=self.school_class,
            title="Test Document",
            document_type="NOTES",
            file=test_file,
            created_by=self.user,
        )
        self.assertEqual(document.school_class, self.school_class)
        self.assertEqual(document.document_type, "NOTES")
        self.assertTrue(os.path.exists(document.file.path))

    def tearDown(self):
        for document in ClassDocument.objects.all():
            if os.path.exists(document.file.path):
                os.remove(document.file.path)


class ClassAttendanceModelTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.user = User.objects.create_user(email="test@test.com", password="testpass")
        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            admission_number="123",
            school=self.school,
        )
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )
        self.school_class.students.add(self.student)

    def test_create_attendance(self):
        attendance = ClassAttendance.objects.create(
            school_class=self.school_class,
            date=timezone.now().date(),
            taken_by=self.user,
        )
        attendance.present_students.add(self.student)

        self.assertEqual(attendance.school_class, self.school_class)
        self.assertEqual(attendance.present_students.count(), 1)
        self.assertEqual(attendance.attendance_rate, 100.0)

    def test_unique_constraint(self):
        date = timezone.now().date()
        ClassAttendance.objects.create(
            school_class=self.school_class, date=date, taken_by=self.user
        )
        with self.assertRaises(ValidationError):
            ClassAttendance.objects.create(
                school_class=self.school_class, date=date, taken_by=self.user
            )


class SchoolStreamModelTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")

    def test_create_stream(self):
        stream = SchoolStream.objects.create(
            school=self.school, name="West", description="West Stream"
        )
        self.assertEqual(stream.school, self.school)
        self.assertEqual(stream.name, "West")

    def test_unique_constraint(self):
        SchoolStream.objects.create(school=self.school, name="West")
        with self.assertRaises(ValidationError):
            SchoolStream.objects.create(school=self.school, name="West")


# python manage.py test skul_data.tests.classes_tests.test_classes_models
