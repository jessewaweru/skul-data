from django.test import TestCase
from rest_framework.exceptions import ValidationError
from skul_data.schools.serializers.schoolclass import (
    SchoolClassSerializer,
    SchoolClassCreateSerializer,
    SchoolClassPromoteSerializer,
    ClassTimetableSerializer,
    ClassDocumentSerializer,
    ClassAttendanceSerializer,
    SchoolStreamSerializer,
)
from skul_data.schools.serializers.schoolstream import (
    SchoolStreamSerializer,
    SchoolStreamCreateSerializer,
)

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
from django.core.files.uploadedfile import SimpleUploadedFile
import os
from skul_data.tests.classes_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_teacher,
)


class SchoolClassSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.stream = SchoolStream.objects.create(school=self.school, name="West")
        self.subject = Subject.objects.create(name="Math", school=self.school)
        self.student = create_test_student(self.school)

        self.class_data = {
            "name": "Grade 1 West",
            "grade_level": "Grade 1",
            "level": "PRIMARY",
            "school": self.school,
            "academic_year": "2023-2024",
            "room_number": "101",
            "capacity": 30,
            "stream": self.stream,
            "class_teacher": self.teacher,
        }
        self.school_class = SchoolClass.objects.create(**self.class_data)
        self.school_class.students.add(self.student)
        self.school_class.subjects.add(self.subject)

    def test_school_class_serializer(self):
        serializer = SchoolClassSerializer(instance=self.school_class)
        data = serializer.data

        self.assertEqual(data["name"], "Grade 1 West")
        self.assertEqual(data["grade_level"], "Grade 1")
        self.assertEqual(data["student_count"], 1)
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(len(data["subjects"]), 1)

    def test_school_class_create_serializer(self):
        data = {
            "name": "Grade 2 West",
            "grade_level": "Grade 2",
            "level": "PRIMARY",
            "academic_year": "2023-2024",
            "room_number": "102",
            "capacity": 30,
            "school": self.school.id,
            "stream": self.stream.id,
            "class_teacher": self.teacher.id,
        }
        serializer = SchoolClassCreateSerializer(
            data=data, context={"request": self._get_request()}
        )
        self.assertTrue(serializer.is_valid())

    def test_school_class_create_duplicate(self):
        # Now try to create a duplicate with the same name/school/year
        duplicate_data = {
            "name": self.class_data["name"],  # Same name
            "grade_level": self.class_data["grade_level"],
            "level": self.class_data["level"],
            "school": self.school,  # Same school
            "academic_year": self.class_data["academic_year"],  # Same year
            "room_number": "102",  # Different room
            "capacity": 25,  # Different capacity
        }
        serializer = SchoolClassCreateSerializer(
            data=duplicate_data, context={"request": self._get_request()}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_class_create_duplicate_grade_stream_year(self):
        """Test that duplicate grade_level/stream/academic_year combinations are prevented"""
        duplicate_data = {
            "name": "Different Name",  # Different name
            "grade_level": self.class_data["grade_level"],  # Same grade
            "level": self.class_data["level"],
            "academic_year": self.class_data["academic_year"],  # Same year
            "room_number": "102",
            "capacity": 25,
            "stream": self.stream.id if self.stream else None,  # Same stream
        }

        serializer = SchoolClassCreateSerializer(
            data=duplicate_data, context={"request": self._get_request()}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_school_class_promote_serializer(self):
        data = {"new_academic_year": "2024-2025"}
        serializer = SchoolClassPromoteSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_school_class_promote_invalid_year(self):
        data = {"new_academic_year": "24"}
        serializer = SchoolClassPromoteSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def _get_request(self):
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.teacher.user
        return request


class ClassTimetableSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

    def test_timetable_serializer(self):
        test_file = SimpleUploadedFile(
            "timetable.pdf", b"file_content", content_type="application/pdf"
        )
        timetable = ClassTimetable.objects.create(
            school_class=self.school_class, file=test_file, description="Test Timetable"
        )

        serializer = ClassTimetableSerializer(instance=timetable)
        data = serializer.data

        self.assertEqual(data["school_class"], self.school_class.id)
        self.assertTrue(data["file"].endswith("timetable.pdf"))

    def tearDown(self):
        for timetable in ClassTimetable.objects.all():
            if os.path.exists(timetable.file.path):
                os.remove(timetable.file.path)


class ClassDocumentSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.user = User.objects.create_user(email="test@test.com", password="testpass")
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

    def test_document_serializer(self):
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

        serializer = ClassDocumentSerializer(instance=document)
        data = serializer.data

        self.assertEqual(data["title"], "Test Document")
        self.assertEqual(data["document_type"], "NOTES")
        self.assertEqual(data["created_by"]["email"], "test@test.com")

    def tearDown(self):
        for document in ClassDocument.objects.all():
            if os.path.exists(document.file.path):
                os.remove(document.file.path)


class ClassAttendanceSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.user = User.objects.create_user(email="test@test.com", password="testpass")
        self.student = create_test_student(self.school)
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )
        self.school_class.students.add(self.student)

    def test_attendance_serializer(self):
        attendance = ClassAttendance.objects.create(
            school_class=self.school_class, date="2023-01-01", taken_by=self.user
        )
        attendance.present_students.add(self.student)

        serializer = ClassAttendanceSerializer(instance=attendance)
        data = serializer.data

        self.assertEqual(data["school_class"], self.school_class.id)
        self.assertEqual(data["date"], "2023-01-01")
        self.assertEqual(len(data["present_students"]), 1)
        self.assertEqual(data["attendance_rate"], 100.0)


class SchoolStreamSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()

    def test_stream_serializer(self):
        stream = SchoolStream.objects.create(
            school=self.school, name="West", description="West Stream"
        )

        serializer = SchoolStreamSerializer(instance=stream)
        data = serializer.data

        self.assertEqual(data["name"], "West")
        self.assertEqual(data["description"], "West Stream")

    def test_stream_create_serializer(self):
        data = {"name": "East", "description": "East Stream"}
        serializer = SchoolStreamCreateSerializer(
            data=data, context={"request": self._get_request()}
        )
        self.assertTrue(serializer.is_valid())

    def test_stream_create_duplicate(self):
        SchoolStream.objects.create(school=self.school, name="West")
        data = {"name": "West", "description": "West Stream"}
        serializer = SchoolStreamCreateSerializer(
            data=data, context={"request": self._get_request()}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def _get_request(self):
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/")
        # Use the admin user created in setUp
        request.user = self.admin_user
        return request


# python manage.py test skul_data.tests.classes_tests.test_classes_serializers
