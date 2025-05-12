from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from skul_data.schools.models.schoolclass import (
    SchoolClass,
    ClassTimetable,
    ClassDocument,
    ClassAttendance,
)
from skul_data.schools.models.schoolstream import SchoolStream
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.students.models.student import Student
from skul_data.schools.models.school import School
from django.core.files.uploadedfile import SimpleUploadedFile
import os


class SchoolClassViewSetTest(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.admin = User.objects.create_user(
            email="admin@test.com", password="testpass", user_type=User.SCHOOL_ADMIN
        )
        self.admin.school_admin_profile.school = self.school
        self.admin.school_admin_profile.save()

        self.teacher = Teacher.objects.create(
            user=User.objects.create_user(
                email="teacher@test.com", password="testpass"
            ),
            school=self.school,
        )
        self.stream = SchoolStream.objects.create(school=self.school, name="West")
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
            "academic_year": "2023-2024",
            "room_number": "101",
            "capacity": 30,
            "stream": self.stream.id,
        }

        self.client = APIClient()

    def test_list_classes_as_admin(self):
        SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse("schoolclass-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_classes_as_teacher(self):
        school_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
            class_teacher=self.teacher,
        )

        self.client.force_authenticate(user=self.teacher.user)
        response = self.client.get(reverse("schoolclass-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_class_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("schoolclass-list"), data=self.class_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SchoolClass.objects.count(), 1)

    def test_create_class_as_teacher_fails(self):
        self.client.force_authenticate(user=self.teacher.user)
        response = self.client.post(
            reverse("schoolclass-list"), data=self.class_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_promote_class(self):
        school_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("schoolclass-promote", kwargs={"pk": school_class.id}),
            data={"new_academic_year": "2024-2025"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SchoolClass.objects.count(), 2)

    def test_assign_teacher(self):
        school_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("schoolclass-assign-teacher", kwargs={"pk": school_class.id}),
            data={"teacher_id": self.teacher.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        school_class.refresh_from_db()
        self.assertEqual(school_class.class_teacher, self.teacher)

    def test_analytics_endpoint(self):
        SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse("schoolclass-analytics"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_classes"], 1)


class ClassTimetableViewSetTest(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.admin = User.objects.create_user(
            email="admin@test.com", password="testpass", user_type=User.SCHOOL_ADMIN
        )
        self.admin.school_admin_profile.school = self.school
        self.admin.school_admin_profile.save()

        self.teacher = Teacher.objects.create(
            user=User.objects.create_user(
                email="teacher@test.com", password="testpass"
            ),
            school=self.school,
        )

        self.school_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
            class_teacher=self.teacher,
        )

        self.client = APIClient()

    def test_create_timetable_as_admin(self):
        test_file = SimpleUploadedFile(
            "timetable.pdf", b"file_content", content_type="application/pdf"
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("classtimetable-list"),
            data={
                "school_class": self.school_class.id,
                "file": test_file,
                "description": "Test Timetable",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ClassTimetable.objects.count(), 1)

    def tearDown(self):
        for timetable in ClassTimetable.objects.all():
            if os.path.exists(timetable.file.path):
                os.remove(timetable.file.path)


class ClassDocumentViewSetTest(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.teacher_user = User.objects.create_user(
            email="teacher@test.com", password="testpass", user_type=User.TEACHER
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, school=self.school
        )

        self.school_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
            class_teacher=self.teacher,
        )

        self.client = APIClient()

    def test_create_document_as_teacher(self):
        test_file = SimpleUploadedFile(
            "document.pdf", b"file_content", content_type="application/pdf"
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            reverse("classdocument-list"),
            data={
                "school_class": self.school_class.id,
                "title": "Test Document",
                "document_type": "NOTES",
                "file": test_file,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ClassDocument.objects.count(), 1)
        self.assertEqual(ClassDocument.objects.first().created_by, self.teacher_user)

    def tearDown(self):
        for document in ClassDocument.objects.all():
            if os.path.exists(document.file.path):
                os.remove(document.file.path)


class ClassAttendanceViewSetTest(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.teacher_user = User.objects.create_user(
            email="teacher@test.com", password="testpass", user_type=User.TEACHER
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, school=self.school
        )

        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            admission_number="123",
            school=self.school,
        )

        self.school_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
            class_teacher=self.teacher,
        )
        self.school_class.students.add(self.student)

        self.client = APIClient()

    def test_create_attendance_as_teacher(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            reverse("classattendance-list"),
            data={"school_class": self.school_class.id, "date": "2023-01-01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ClassAttendance.objects.count(), 1)
        self.assertEqual(ClassAttendance.objects.first().taken_by, self.teacher_user)

    def test_mark_attendance(self):
        attendance = ClassAttendance.objects.create(
            school_class=self.school_class,
            date="2023-01-01",
            taken_by=self.teacher_user,
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            reverse("classattendance-mark-attendance", kwargs={"pk": attendance.id}),
            data={"student_ids": [self.student.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(attendance.present_students.count(), 1)


class SchoolStreamViewSetTest(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.admin = User.objects.create_user(
            email="admin@test.com", password="testpass", user_type=User.SCHOOL_ADMIN
        )
        self.admin.school_admin_profile.school = self.school
        self.admin.school_admin_profile.save()

        self.client = APIClient()

    def test_create_stream_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("schoolstream-list"),
            data={"name": "West", "description": "West Stream"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SchoolStream.objects.count(), 1)

    def test_create_duplicate_stream_fails(self):
        SchoolStream.objects.create(school=self.school, name="West")

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("schoolstream-list"),
            data={"name": "West", "description": "West Stream"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# python manage.py test skul_data.tests.classes_tests.test_classes_views
