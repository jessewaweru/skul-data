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
    StudentDocument,
    StudentNote,
    Subject,
)
from skul_data.tests.students_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_teacher,
    create_test_parent,
    create_test_class,
    get_last_action_log,
)
from skul_data.action_logs.models.action_log import ActionCategory
import csv


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

    def test_create_student_logging(self):
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

        # Verify the log was created
        log = get_last_action_log()
        self.assertIsNotNone(log, "No action log was created")
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.CREATE)
        self.assertEqual(log.action, f"POST /students/students/")

        # Get the latest student
        latest_student = Student.objects.latest("id")
        self.assertEqual(log.content_object, latest_student)
        self.assertEqual(log.metadata["fields_changed"], None)  # For create operations

    def test_promote_student_logging(self):
        new_class = create_test_class(self.school, name="Form 2")
        url = reverse("students-promote", args=[self.student.id])
        data = {"new_class_id": new_class.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify the promotion log
        log = get_last_action_log()
        self.assertIsNotNone(log, "No action log was created")
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.UPDATE)
        self.assertIn(f"Promoted student {self.student}", log.action)
        self.assertEqual(log.content_object, self.student)
        self.assertEqual(log.metadata["new_class_name"], "Form 2")
        self.assertEqual(log.metadata["old_class_name"], self.school_class.name)

    def test_deactivate_student_logging(self):
        url = reverse("students-deactivate", args=[self.student.id])
        response = self.client.post(url, {"reason": "Test deactivation"}, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify deactivation log
        log = get_last_action_log()
        self.assertIsNotNone(log, "No action log was created")
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.UPDATE)
        self.assertIn(f"Deactivated student {self.student}", log.action)
        self.assertEqual(log.content_object, self.student)
        self.assertEqual(log.metadata["reason"], "Test deactivation")
        self.assertEqual(log.metadata["previous_status"], StudentStatus.ACTIVE)

    def test_bulk_create_logging(self):
        # Create proper CSV content as bytes - include student_class_id if required
        csv_content = "first_name,last_name,date_of_birth,gender,parent_id\nTest,Student,2010-01-01,M,{}\n".format(
            self.parent.id
        )

        # Create a proper file-like object
        from django.core.files.uploadedfile import SimpleUploadedFile

        csv_file = SimpleUploadedFile(
            "test_students.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        url = reverse("students-bulk-create")
        response = self.client.post(url, {"file": csv_file}, format="multipart")

        # Debug output
        if response.status_code != 201:
            print("Bulk create errors:", response.data)

        self.assertEqual(response.status_code, 201)

        # Verify bulk create log
        log = get_last_action_log()
        self.assertIsNotNone(log, "No action log was created")
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.CREATE)
        self.assertIn("Bulk created", log.action)  # This should now match
        self.assertEqual(log.metadata["created_count"], 1)
        self.assertEqual(log.metadata["error_count"], 0)


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

    def test_create_attendance_logging(self):
        url = reverse("student-attendance-list")
        data = {
            "student": self.student.id,
            "date": timezone.now().date().isoformat(),
            "status": "PRESENT",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)

        # Verify attendance log
        log = get_last_action_log()
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.UPDATE)
        self.assertIn("Recorded attendance", log.action)
        self.assertEqual(log.content_object, StudentAttendance.objects.last())
        self.assertEqual(log.metadata["status"], "PRESENT")

    def test_bulk_attendance_logging(self):
        url = reverse("student-attendance-bulk-create")
        data = {
            "date": timezone.now().date().isoformat(),
            "student_statuses": [{"student_id": self.student.id, "status": "PRESENT"}],
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify bulk attendance log
        log = get_last_action_log()
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.UPDATE)
        self.assertIn("Recorded bulk attendance", log.action)
        self.assertEqual(log.metadata["created_count"], 1)
        self.assertEqual(log.metadata["date"], timezone.now().date().isoformat())


class StudentDocumentViewSetLoggingTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)
        self.client.force_authenticate(user=self.admin)

    def test_document_upload_logging(self):
        from io import BytesIO

        test_file = BytesIO(b"test document content")
        test_file.name = "test.pdf"

        url = reverse("student-documents-list")
        data = {
            "student": self.student.id,
            "title": "Test Document",
            "document_type": "BIRTH_CERTIFICATE",
            "file": test_file,
        }
        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, 201)

        # Verify document upload log
        log = get_last_action_log()
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.UPLOAD)
        self.assertIn("Uploaded document", log.action)
        self.assertEqual(log.content_object, StudentDocument.objects.last())
        self.assertEqual(log.metadata["document_type"], "BIRTH_CERTIFICATE")


class StudentNoteViewSetLoggingTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)
        self.client.force_authenticate(user=self.admin)

    def test_note_creation_logging(self):
        url = reverse("student-notes-list")
        data = {
            "student": self.student.id,
            "note_type": "ACADEMIC",
            "content": "Test note content",
            "is_private": False,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)

        # Verify note creation log
        log = get_last_action_log()
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.CREATE)
        self.assertIn("Added ACADEMIC note", log.action)
        self.assertEqual(log.content_object, StudentNote.objects.last())
        self.assertEqual(log.metadata["note_type"], "ACADEMIC")

    def test_note_update_logging(self):
        note = StudentNote.objects.create(
            student=self.student,
            note_type="ACADEMIC",
            content="Original content",
            created_by=self.admin,
        )

        url = reverse("student-notes-detail", args=[note.id])
        data = {"content": "Updated content"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify note update log
        log = get_last_action_log()
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.UPDATE)
        self.assertIn("Updated note", log.action)
        self.assertEqual(log.content_object, note)
        self.assertEqual(log.metadata["changes"]["content"]["old"], "Original content")
        self.assertEqual(log.metadata["changes"]["content"]["new"], "Updated content")


class SubjectViewSetLoggingTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

    def test_subject_creation_logging(self):
        url = reverse("subjects-list")
        data = {
            "name": "Mathematics",
            "code": "MATH",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)

        # Verify subject creation log
        log = get_last_action_log()
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.CREATE)
        self.assertIn("Created new subject Mathematics", log.action)
        self.assertEqual(log.content_object, Subject.objects.last())
        self.assertEqual(log.metadata["code"], "MATH")


# python manage.py test skul_data.tests.students_tests.test_students_views
