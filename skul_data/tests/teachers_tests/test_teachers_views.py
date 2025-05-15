from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Subject
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.tests.teachers_tests.test_helpers import (
    create_test_teacher,
    create_test_teacher_workload,
    create_test_teacher_attendance,
    create_test_teacher_document,
    create_test_school,
)
from datetime import date


class TeacherViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.subject = Subject.objects.create(
            name="Mathematics", code="MATH", school=self.school
        )
        self.school_class = SchoolClass.objects.create(
            name="Form 1",
            grade_level="Form 1",
            school=self.school,
            academic_year="2023",
        )
        self.teacher = create_test_teacher(self.school, email="teacher1@test.com")
        self.teacher2 = create_test_teacher(self.school, email="teacher2@test.com")

        # Create a teacher user to test permissions
        self.teacher_user = User.objects.create_user(
            email="teacheruser@test.com",
            username="teacheruser",
            password="testpass",
            user_type=User.TEACHER,
        )
        self.teacher_profile = Teacher.objects.create(
            user=self.teacher_user, school=self.school
        )

    def test_list_teachers(self):
        url = reverse("teacher-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_count = Teacher.objects.count()
        self.assertEqual(len(response.data), expected_count)

    def test_retrieve_teacher(self):
        url = reverse("teacher-detail", args=[self.teacher.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "teacher1@test.com")

    def test_create_teacher(self):
        url = reverse("teacher-list")
        user = User.objects.create_user(
            email="newteacher@test.com",
            username="newteacher",
            password="testpass",
            first_name="New",
            last_name="Teacher",
            user_type=User.TEACHER,
        )

        data = {
            "user_id": user.id,
            "school": self.school.id,
            "phone_number": "+254711111111",
            "status": "ACTIVE",
            "qualification": "B.Ed",
            "specialization": "English",
            "years_of_experience": 3,
            "subject_ids": [self.subject.id],
            "class_ids": [self.school_class.id],
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["first_name"], "New")

    def test_update_teacher(self):
        url = reverse("teacher-detail", args=[self.teacher.id])
        data = {
            "first_name": "Updated",
            "last_name": "Teacher",
            "qualification": "M.Ed",
            "specialization": "Mathematics",
        }

        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["qualification"], "M.Ed")

    def test_delete_teacher(self):
        url = reverse("teacher-detail", args=[self.teacher.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_change_status_action(self):
        url = reverse("teacher-change-status", args=[self.teacher.id])
        data = {"status": "TERMINATED", "termination_date": "2023-12-31"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "TERMINATED")

    def test_assign_classes_action(self):
        url = reverse("teacher-assign-classes", args=[self.teacher.id])
        data = {"class_ids": [self.school_class.id], "action": "ADD"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["assigned_classes_ids"]), 1)

    def test_assign_subjects_action(self):
        url = reverse("teacher-assign-subjects", args=[self.teacher.id])
        data = {"subject_ids": [self.subject.id], "action": "ADD"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["subjects_taught"]), 1)

    def test_analytics_action(self):
        url = reverse("teacher-analytics")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_teachers", response.data)

    def test_teacher_permissions(self):
        # Test teacher can only see their own profile
        self.client.force_authenticate(user=self.teacher_user)

        # Should be able to see own profile
        url = reverse("teacher-detail", args=[self.teacher_profile.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should not be able to see other teachers
        url = reverse("teacher-detail", args=[self.teacher.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TeacherWorkloadViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.subject = Subject.objects.create(
            name="Mathematics", code="MATH", school=self.school
        )
        self.school_class = SchoolClass.objects.create(
            name="Form 1",
            grade_level="Form 1",
            school=self.school,
            academic_year="2023",
        )
        self.teacher = create_test_teacher(self.school)
        self.workload = create_test_teacher_workload(
            self.teacher, self.school_class, self.subject
        )

    def test_list_workloads(self):
        url = reverse("teacher-workload-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_workload(self):
        url = reverse("teacher-workload-detail", args=[self.workload.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["hours_per_week"], 10)

    def test_create_workload(self):
        url = reverse("teacher-workload-list")
        data = {
            "teacher_id": self.teacher.id,
            "school_class_id": self.school_class.id,
            "subject_id": self.subject.id,
            "hours_per_week": 15,
            "term": "Term 2",
            "school_year": "2024",
        }
        response = self.client.post(url, data, format="json")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["hours_per_week"], 15)

    def test_update_workload(self):
        url = reverse("teacher-workload-detail", args=[self.workload.id])
        data = {"hours_per_week": 12}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["hours_per_week"], 12)

    def test_delete_workload(self):
        url = reverse("teacher-workload-detail", args=[self.workload.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_teacher_filtering(self):
        # Create another teacher and workload
        teacher2 = create_test_teacher(self.school, email="teacher2@test.com")
        workload2 = create_test_teacher_workload(
            teacher2, self.school_class, self.subject
        )

        url = f"{reverse('teacher-workload-list')}?teacher={self.teacher.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["teacher"]["id"], self.teacher.id)


class TeacherAttendanceViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.teacher = create_test_teacher(self.school)
        self.attendance = create_test_teacher_attendance(self.teacher)

    def test_list_attendances(self):
        url = reverse("teacher-attendance-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_attendance(self):
        url = reverse("teacher-attendance-detail", args=[self.attendance.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "PRESENT")

    def test_create_attendance(self):
        url = reverse("teacher-attendance-list")
        data = {
            "teacher_id": self.teacher.id,
            "date": "2023-01-02",
            "status": "ABSENT",
            "recorded_by_id": self.admin.id,
        }
        response = self.client.post(url, data, format="json")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "ABSENT")

    def test_update_attendance(self):
        url = reverse("teacher-attendance-detail", args=[self.attendance.id])
        data = {"status": "LATE", "notes": "Arrived 15 minutes late"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "LATE")

    def test_delete_attendance(self):
        url = reverse("teacher-attendance-detail", args=[self.attendance.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_date_filtering(self):
        # Create attendance with different date
        attendance2 = create_test_teacher_attendance(
            self.teacher, date=date(2023, 1, 2)
        )

        url = f"{reverse('teacher-attendance-list')}?date={self.attendance.date}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.attendance.id)


class TeacherDocumentViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.teacher = create_test_teacher(self.school)
        self.document = create_test_teacher_document(self.teacher, self.admin)

    def test_list_documents(self):
        url = reverse("teacher-document-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_document(self):
        url = reverse("teacher-document-detail", args=[self.document.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Test Document")

    def test_create_document(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse("teacher-document-list")
        file = SimpleUploadedFile("test.pdf", b"test content")

        data = {
            "teacher_id": self.teacher.id,
            "title": "New Document",
            "document_type": "CONTRACT",
            "file": file,
            "uploaded_by_id": self.admin.id,
            "is_confidential": True,
        }
        response = self.client.post(url, data, format="multipart")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Document")

    def test_update_document(self):
        url = reverse("teacher-document-detail", args=[self.document.id])
        data = {"title": "Updated Document", "is_confidential": True}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Document")

    def test_delete_document(self):
        url = reverse("teacher-document-detail", args=[self.document.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_document_type_filtering(self):
        # Create document with different type
        document2 = create_test_teacher_document(
            self.teacher, self.admin, document_type="CV"
        )

        url = f"{reverse("teacher-document-list")}?document_type=QUALIFICATION"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.document.id)


# python manage.py test skul_data.tests.teachers_tests.test_teachers_views
