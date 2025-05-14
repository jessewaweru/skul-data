# students/tests/test_viewsets.py
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta
from skul_data.users.models.base_user import User
from skul_data.students.models.student import (
    Student,
    StudentStatus,
    StudentAttendance,
    AttendanceStatus,
)
from skul_data.tests.students_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_teacher,
    create_test_parent,
    create_test_class,
)


class StudentViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.school_class = create_test_class(self.school)
        self.teacher = create_test_teacher(self.school)

        # IMPORTANT FIX: Explicitly assign teacher to class
        self.school_class.class_teacher = self.teacher
        self.school_class.save()

        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, student_class=self.school_class)

        # Assign parent to student
        self.student.parent = self.parent
        self.student.save()

        # Login as admin
        self.client.force_authenticate(user=self.admin)

    def test_list_students(self):
        url = reverse("students-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_create_student(self):
        url = reverse("students-list")
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "date_of_birth": (
                timezone.now().date() - timedelta(days=365 * 12)
            ).isoformat(),
            "gender": "F",
            "student_class_id": self.school_class.id,
            "parent_id": self.parent.id,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Student.objects.count(), 2)

    def test_retrieve_student(self):
        url = reverse("students-detail", args=[self.student.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["full_name"], "John Doe")

    def test_promote_student(self):
        new_class = create_test_class(self.school, name="Form 2")
        url = reverse("students-promote", args=[self.student.id])
        data = {"new_class_id": new_class.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_class, new_class)

    def test_deactivate_student(self):
        url = reverse("students-deactivate", args=[self.student.id])
        response = self.client.post(url, {"reason": "Test deactivation"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.assertEqual(self.student.status, StudentStatus.LEFT)

    def test_restore_student(self):
        self.student.deactivate("Test deactivation")
        url = reverse("students-restore", args=[self.student.id])
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertEqual(self.student.status, StudentStatus.ACTIVE)

    def test_teacher_access(self):
        # Login as teacher
        self.client.force_authenticate(user=self.teacher.user)

        url = reverse("students-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)  # Should see student in their class

    def test_parent_access(self):
        # Login as parent
        self.client.force_authenticate(user=self.parent.user)

        url = reverse("students-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


class StudentAttendanceViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.school_class = create_test_class(self.school)
        self.school_class.class_teacher = self.teacher  # Assign teacher to class
        self.school_class.save()
        self.student = create_test_student(self.school, student_class=self.school_class)

        # IMPORTANT FIX: Make sure admin has proper permissions
        self.admin.user_type = User.SCHOOL_ADMIN
        self.admin.save()

        self.client.force_authenticate(user=self.admin)

    def test_create_attendance(self):
        url = reverse("student-attendance-list")
        data = {
            "student": self.student.id,
            "date": timezone.now().date().isoformat(),
            "status": "PRESENT",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(StudentAttendance.objects.count(), 1)

    def test_bulk_attendance(self):
        url = reverse("student-attendance-bulk-create")
        data = {
            "date": timezone.now().date().isoformat(),
            "student_statuses": [{"student_id": self.student.id, "status": "PRESENT"}],
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StudentAttendance.objects.count(), 1)

    def test_class_attendance(self):
        # Create attendance record
        StudentAttendance.objects.create(
            student=self.student,
            date=timezone.now().date(),
            status=AttendanceStatus.PRESENT,
            recorded_by=self.admin,
        )

        url = reverse("student-attendance-class-attendance")
        response = self.client.get(url, {"class_id": self.student.student_class.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_teacher_access(self):
        # Login as teacher
        self.client.force_authenticate(user=self.teacher.user)

        url = reverse("student-attendance-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# python manage.py test skul_data.tests.students_tests.test_students_views
