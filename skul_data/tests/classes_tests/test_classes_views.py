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
from django.core.files.uploadedfile import SimpleUploadedFile
import os
from skul_data.tests.classes_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_teacher,
)


class SchoolClassViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.stream = SchoolStream.objects.create(school=self.school, name="West")

        # Make sure school is included in class_data
        self.class_data = {
            "name": "Grade 1 West",
            "grade_level": "Grade 1",
            "level": "PRIMARY",
            "academic_year": "2023-2024",
            "room_number": "101",
            "capacity": 30,
            "stream": self.stream.id,
            "school": self.school.id,  # Explicitly include school ID
        }

    def test_create_class_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        print(f"Request user: {self.admin.id}, is_staff: {self.admin.is_staff}")
        print(f"Request data: {self.class_data}")

        response = self.client.post(
            reverse("schools:class-list"),
            data=self.class_data,
            format="json",
        )
        print(f"Response: {response.status_code}, {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_classes_as_teacher(self):
        school_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
            class_teacher=self.teacher,
        )

        self.client.force_authenticate(user=self.teacher.user)
        response = self.client.get(reverse("schools:class-list"))  # Updated URL name
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_class_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("schools:class-list"),  # Updated URL name
            data=self.class_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SchoolClass.objects.count(), 1)

    def test_create_class_as_teacher_fails(self):
        self.client.force_authenticate(user=self.teacher.user)
        response = self.client.post(
            reverse("schools:class-list"),  # Updated URL name
            data=self.class_data,
            format="json",
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
            reverse(
                "schools:class-promote", kwargs={"pk": school_class.id}
            ),  # Updated URL name
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
            reverse(
                "schools:class-assign-teacher", kwargs={"pk": school_class.id}
            ),  # Updated URL name
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
        response = self.client.get(
            reverse("schools:class-analytics")
        )  # Updated URL name
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_classes"], 1)


class ClassTimetableViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)

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
            reverse("schools:class-timetable-list"),  # Updated URL name
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
        self.school, _ = create_test_school()
        self.teacher = create_test_teacher(self.school)

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

        self.client.force_authenticate(user=self.teacher.user)
        response = self.client.post(
            reverse("schools:class-document-list"),  # Updated URL name
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
        self.assertEqual(ClassDocument.objects.first().created_by, self.teacher.user)

    def tearDown(self):
        for document in ClassDocument.objects.all():
            if os.path.exists(document.file.path):
                os.remove(document.file.path)


class ClassAttendanceViewSetTest(APITestCase):
    from skul_data.students.models.student import Student

    def setUp(self):
        self.school, _ = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.student = create_test_student(self.school)

        self.school_class = SchoolClass.objects.create(
            name="Grade 1 West",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
            class_teacher=self.teacher,
        )
        # Properly assign student to class
        self.student.student_class = self.school_class
        self.student.save()

    def test_create_attendance_as_teacher(self):
        self.client.force_authenticate(user=self.teacher.user)
        response = self.client.post(
            reverse("schools:class-attendance-list"),  # Updated URL name
            data={"school_class": self.school_class.id, "date": "2023-01-01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ClassAttendance.objects.count(), 1)
        self.assertEqual(ClassAttendance.objects.first().taken_by, self.teacher.user)

    def test_mark_attendance(self):
        attendance = ClassAttendance.objects.create(
            school_class=self.school_class,
            date="2023-01-01",
            taken_by=self.teacher.user,
        )

        self.client.force_authenticate(user=self.teacher.user)
        response = self.client.post(
            reverse(
                "schools:class-attendance-mark-attendance", kwargs={"pk": attendance.id}
            ),  # Updated URL name
            data={"student_ids": [self.student.id]},
            format="json",
        )
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(attendance.present_students.count(), 1)


class SchoolStreamViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.client = APIClient()

    def test_create_stream_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("schools:stream-list"),  # Updated URL name
            data={"name": "West", "description": "West Stream"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SchoolStream.objects.count(), 1)

    def test_create_duplicate_stream_fails(self):
        SchoolStream.objects.create(school=self.school, name="West")

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("schools:stream-list"),  # Updated URL name
            data={"name": "West", "description": "West Stream"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# python manage.py test skul_data.tests.classes_tests.test_classes_views
