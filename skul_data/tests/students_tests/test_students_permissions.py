# students/tests/test_permissions.py
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from skul_data.students.models.student import Student
from skul_data.tests.students_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_teacher,
    create_test_parent,
)


class StudentPermissionsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school)

    def test_admin_permissions(self):
        self.client.force_authenticate(user=self.admin)

        # Test create
        url = reverse("students-list")
        response = self.client.post(url, {}, format="json")
        self.assertNotEqual(response.status_code, 403)  # Should have permission

        # Test update
        url = reverse("students-detail", args=[self.student.id])
        response = self.client.patch(url, {}, format="json")
        self.assertNotEqual(response.status_code, 403)

        # Test delete
        response = self.client.delete(url, format="json")
        self.assertNotEqual(response.status_code, 403)

    def test_teacher_permissions(self):
        self.client.force_authenticate(user=self.teacher.user)

        # Test list (should have read-only access)
        url = reverse("students-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test create (should not have permission)
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, 403)

        # Test update (should not have permission)
        url = reverse("students-detail", args=[self.student.id])
        response = self.client.patch(url, {}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_parent_permissions(self):
        # Parent should only see their own children
        self.client.force_authenticate(user=self.parent.user)

        # Initially shouldn't see any students
        url = reverse("students-list")
        response = self.client.get(url)
        self.assertEqual(len(response.data), 0)

        # Assign student to parent
        self.student.parent = self.parent
        self.student.save()

        # Now should see their child
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)

        # Should not be able to create/update
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, 403)


class StudentAttendancePermissionsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school)

    def test_teacher_attendance_permissions(self):
        self.client.force_authenticate(user=self.teacher.user)

        # Teacher should be able to create attendance
        url = reverse("student-attendance-list")
        data = {
            "student": self.student.id,
            "date": "2023-01-01",
            "status": "PRESENT",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)

        # Teacher should be able to bulk create
        url = reverse("student-attendance-bulk-create")
        data = {
            "date": "2023-01-01",
            "student_statuses": [{"student_id": self.student.id, "status": "PRESENT"}],
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

    def test_parent_attendance_permissions(self):
        self.client.force_authenticate(user=self.parent.user)

        # Parent should only be able to view
        url = reverse("student-attendance-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Should not be able to create
        data = {
            "student": self.student.id,
            "date": "2023-01-01",
            "status": "PRESENT",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 403)


# python manage.py test skul_data.tests.students_tests.test_students_permissions
