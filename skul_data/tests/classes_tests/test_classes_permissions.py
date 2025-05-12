from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile
import os
from rest_framework import status
from skul_data.schools.models.schoolclass import (
    SchoolClass,
    ClassTimetable,
    ClassDocument,
)
from skul_data.schools.models.schoolstream import SchoolStream
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.schools.models.school import School


class ClassPermissionsTest(APITestCase):
    def setUp(self):
        # Create schools
        self.school1 = School.objects.create(name="Test School 1")
        self.school2 = School.objects.create(name="Test School 2")

        # Create admin users
        self.school1_admin = User.objects.create_user(
            email="admin1@test.com", password="testpass", user_type=User.SCHOOL_ADMIN
        )
        self.school1_admin.school_admin_profile.school = self.school1
        self.school1_admin.school_admin_profile.save()

        self.school2_admin = User.objects.create_user(
            email="admin2@test.com", password="testpass", user_type=User.SCHOOL_ADMIN
        )
        self.school2_admin.school_admin_profile.school = self.school2
        self.school2_admin.school_admin_profile.save()

        # Create teachers
        self.school1_teacher = Teacher.objects.create(
            user=User.objects.create_user(
                email="teacher1@test.com", password="testpass"
            ),
            school=self.school1,
        )
        self.school2_teacher = Teacher.objects.create(
            user=User.objects.create_user(
                email="teacher2@test.com", password="testpass"
            ),
            school=self.school2,
        )

        # Create parent user (should have no access)
        self.parent = User.objects.create_user(
            email="parent@test.com", password="testpass", user_type=User.PARENT
        )

        # Create test data
        self.stream1 = SchoolStream.objects.create(school=self.school1, name="West")
        self.stream2 = SchoolStream.objects.create(school=self.school2, name="East")

        self.school1_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school1,
            academic_year="2023-2024",
            class_teacher=self.school1_teacher,
            stream=self.stream1,
        )

        self.school2_class = SchoolClass.objects.create(
            name="Grade 1 East",
            grade_level="Grade 1",
            school=self.school2,
            academic_year="2023-2024",
            stream=self.stream2,
        )

        # Create a class with no teacher assigned
        self.unassigned_class = SchoolClass.objects.create(
            name="Grade 2 West",
            grade_level="Grade 2",
            school=self.school1,
            academic_year="2023-2024",
        )

        self.client = APIClient()

    # ================ SchoolClass Permissions ================

    def test_admin_can_access_own_school_classes(self):
        self.client.force_authenticate(user=self.school1_admin)
        response = self.client.get(reverse("schoolclass-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # school1_class and unassigned_class

    def test_admin_cannot_access_other_school_classes(self):
        self.client.force_authenticate(user=self.school1_admin)
        response = self.client.get(
            reverse("schoolclass-detail", kwargs={"pk": self.school2_class.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_teacher_can_access_assigned_classes(self):
        self.client.force_authenticate(user=self.school1_teacher.user)
        response = self.client.get(reverse("schoolclass-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # Only their assigned class
        self.assertEqual(response.data[0]["id"], self.school1_class.id)

    def test_teacher_cannot_access_unassigned_classes(self):
        self.client.force_authenticate(user=self.school1_teacher.user)
        response = self.client.get(
            reverse("schoolclass-detail", kwargs={"pk": self.unassigned_class.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_parent_cannot_access_classes(self):
        self.client.force_authenticate(user=self.parent)
        response = self.client.get(reverse("schoolclass-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_access_classes(self):
        response = self.client.get(reverse("schoolclass-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ================ ClassTimetable Permissions ================

    def test_admin_can_manage_own_school_timetables(self):
        self.client.force_authenticate(user=self.school1_admin)
        test_file = SimpleUploadedFile(
            "timetable.pdf", b"file_content", content_type="application/pdf"
        )
        response = self.client.post(
            reverse("classtimetable-list"),
            data={
                "school_class": self.school1_class.id,
                "file": test_file,
                "description": "Test Timetable",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_teacher_can_view_assigned_class_timetables(self):
        timetable = ClassTimetable.objects.create(
            school_class=self.school1_class,
            file=SimpleUploadedFile(
                "timetable.pdf", b"file_content", content_type="application/pdf"
            ),
            description="Test Timetable",
        )

        self.client.force_authenticate(user=self.school1_teacher.user)
        response = self.client.get(
            reverse("classtimetable-detail", kwargs={"pk": timetable.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_teacher_cannot_manage_timetables(self):
        self.client.force_authenticate(user=self.school1_teacher.user)
        test_file = SimpleUploadedFile(
            "timetable.pdf", b"file_content", content_type="application/pdf"
        )
        response = self.client.post(
            reverse("classtimetable-list"),
            data={
                "school_class": self.school1_class.id,
                "file": test_file,
                "description": "Test Timetable",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ================ ClassDocument Permissions ================

    def test_teacher_can_create_documents_for_assigned_classes(self):
        self.client.force_authenticate(user=self.school1_teacher.user)
        test_file = SimpleUploadedFile(
            "document.pdf", b"file_content", content_type="application/pdf"
        )
        response = self.client.post(
            reverse("classdocument-list"),
            data={
                "school_class": self.school1_class.id,
                "title": "Test Document",
                "document_type": "NOTES",
                "file": test_file,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_teacher_cannot_create_documents_for_unassigned_classes(self):
        self.client.force_authenticate(user=self.school1_teacher.user)
        test_file = SimpleUploadedFile(
            "document.pdf", b"file_content", content_type="application/pdf"
        )
        response = self.client.post(
            reverse("classdocument-list"),
            data={
                "school_class": self.unassigned_class.id,
                "title": "Test Document",
                "document_type": "NOTES",
                "file": test_file,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ================ ClassAttendance Permissions ================

    def test_teacher_can_take_attendance_for_assigned_classes(self):
        self.client.force_authenticate(user=self.school1_teacher.user)
        response = self.client.post(
            reverse("classattendance-list"),
            data={"school_class": self.school1_class.id, "date": "2023-01-01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_teacher_cannot_take_attendance_for_unassigned_classes(self):
        self.client.force_authenticate(user=self.school1_teacher.user)
        response = self.client.post(
            reverse("classattendance-list"),
            data={"school_class": self.unassigned_class.id, "date": "2023-01-01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ================ SchoolStream Permissions ================

    def test_only_admin_can_manage_streams(self):
        # Teacher cannot create streams
        self.client.force_authenticate(user=self.school1_teacher.user)
        response = self.client.post(
            reverse("schoolstream-list"),
            data={"name": "New Stream", "description": "Test Stream"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin can create streams
        self.client.force_authenticate(user=self.school1_admin)
        response = self.client.post(
            reverse("schoolstream-list"),
            data={"name": "New Stream", "description": "Test Stream"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_cannot_manage_other_school_streams(self):
        self.client.force_authenticate(user=self.school1_admin)
        response = self.client.get(
            reverse("schoolstream-detail", kwargs={"pk": self.stream2.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def tearDown(self):
        # Clean up any uploaded files
        for timetable in ClassTimetable.objects.all():
            if os.path.exists(timetable.file.path):
                os.remove(timetable.file.path)
        for document in ClassDocument.objects.all():
            if os.path.exists(document.file.path):
                os.remove(document.file.path)


# python manage.py test skul_data.tests.classes_tests.test_classes_permissions
