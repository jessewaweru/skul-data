from datetime import time
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.tests.teachers_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_teacher_document,
    create_test_teacher_attendance,
)
from skul_data.students.models.student import Subject
from skul_data.schools.models.schoolclass import SchoolClass
from unittest.mock import patch
from skul_data.users.views.teacher import TeacherDocumentViewSet
from django.db.models import Q


class TeacherDocumentLoggingTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        # Create a test document
        self.document = create_test_teacher_document(
            self.teacher,
            self.admin,
            title="Test Contract",
            document_type="CONTRACT",
            is_confidential=True,
        )

    def test_document_deletion_logging(self):
        url = reverse("teacher-document-detail", args=[self.document.id])
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Check the action log was created
        log = ActionLog.objects.filter(
            category="DELETE", content_type__model="teacherdocument"
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.action, "Deleted teacher document: Test Contract")
        self.assertEqual(log.user, self.admin)
        # Note: content_object will be None after deletion since the object no longer exists

        # Verify metadata
        self.assertEqual(log.metadata["document_type"], "CONTRACT")
        self.assertEqual(log.metadata["teacher_id"], self.teacher.id)
        self.assertTrue(log.metadata["was_confidential"])

    def test_log_created_even_if_document_deletion_fails(self):
        # Mock the perform_destroy method to raise an exception
        with patch.object(
            TeacherDocumentViewSet,
            "perform_destroy",
            side_effect=Exception("Simulated failure"),
        ):
            url = reverse("teacher-document-detail", args=[self.document.id])

            response = self.client.delete(url)

            # Should return 500 error
            self.assertEqual(
                response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR
            )

            # Verify log was still created
            log = ActionLog.objects.filter(
                category="DELETE", content_type__model="teacherdocument"
            ).first()
            self.assertIsNotNone(log)


class TeacherAttendanceLoggingTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.attendance = create_test_teacher_attendance(
            self.teacher, status="PRESENT", check_in=time(8, 0), check_out=time(16, 0)
        )

    def test_attendance_update_logging(self):
        url = reverse("teacher-attendance-detail", args=[self.attendance.id])
        data = {"status": "LATE", "check_in": "08:30:00", "notes": "Arrived late"}

        with patch(
            "skul_data.users.serializers.teacher.TeacherAttendanceSerializer.update"
        ) as mock_update:
            mock_update.return_value = self.attendance
            response = self.client.patch(url, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            mock_update.assert_called_once()

    def test_no_log_for_unmodified_fields(self):
        url = reverse("teacher-attendance-detail", args=[self.attendance.id])
        data = {"notes": "No important changes"}

        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # No log should be created since no tracked fields changed
        log_count = ActionLog.objects.filter(
            category="UPDATE", content_type__model="teacherattendance"
        ).count()

        self.assertEqual(log_count, 0)


class TeacherStatusLoggingTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_status_change_to_terminated_logging(self):
        url = reverse("teacher-change-status", args=[self.teacher.id])
        data = {
            "status": "TERMINATED",
            "termination_date": timezone.now().date().isoformat(),
        }

        # Set the current user on the teacher instance for the signal
        self.teacher._current_user = self.admin

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh objects
        self.teacher.refresh_from_db()
        self.teacher.user.refresh_from_db()

        # Should have two logs - status change and user deactivation
        logs = ActionLog.objects.filter(
            Q(content_type__model="teacher") | Q(content_type__model="user")
        ).order_by("timestamp")

        self.assertEqual(logs.count(), 2)

        # First log - status change
        status_log = logs[0]
        self.assertEqual(
            status_log.action, "Changed teacher status from ACTIVE to TERMINATED"
        )
        self.assertEqual(status_log.metadata["previous_status"], "ACTIVE")
        self.assertEqual(status_log.metadata["new_status"], "TERMINATED")

        # Second log - user deactivation
        user_logs = ActionLog.objects.filter(
            content_type__model="user",
            action="Deactivated user account due to teacher termination",
        )
        self.assertEqual(user_logs.count(), 1)

    def test_status_change_from_terminated_logging(self):
        # First terminate the teacher
        self.teacher.status = "TERMINATED"
        self.teacher.termination_date = timezone.now().date()
        self.teacher._current_user = self.admin
        self.teacher.save()

        # Clear existing logs to focus on reactivation
        ActionLog.objects.all().delete()

        # Now reactivate
        url = reverse("teacher-change-status", args=[self.teacher.id])
        data = {"status": "ACTIVE"}

        # Set the current user on the teacher instance for the signal
        self.teacher._current_user = self.admin

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh objects
        self.teacher.refresh_from_db()
        self.teacher.user.refresh_from_db()

        # Should have logs for reactivation
        status_log = ActionLog.objects.filter(
            content_type__model="teacher",
            action="Changed teacher status from TERMINATED to ACTIVE",
        ).first()
        self.assertIsNotNone(status_log)

        user_log = ActionLog.objects.filter(
            content_type__model="user",
            action="Reactivated user account due to teacher status change",
        ).first()
        self.assertIsNotNone(user_log)

    def test_no_duplicate_user_deactivation(self):
        # Set to terminated first
        self.teacher.status = "TERMINATED"
        self.teacher.termination_date = timezone.now().date()
        self.teacher._current_user = self.admin
        self.teacher.save()

        # Try terminating again
        url = reverse("teacher-change-status", args=[self.teacher.id])
        data = {
            "status": "TERMINATED",
            "termination_date": timezone.now().date().isoformat(),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only have one user deactivation log (from initial termination)
        user_logs = ActionLog.objects.filter(
            action__contains="Deactivated user account"
        ).count()

        self.assertEqual(user_logs, 1)


class TeacherSubjectAssignmentLoggingTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        # Create test subjects
        self.math = Subject.objects.create(
            name="Mathematics", code="MATH", school=self.school
        )
        self.english = Subject.objects.create(
            name="English", code="ENG", school=self.school
        )
        self.science = Subject.objects.create(
            name="Science", code="SCI", school=self.school
        )

    def test_add_subjects_logging(self):
        url = reverse("teacher-assign-subjects", args=[self.teacher.id])
        data = {"subject_ids": [self.math.id, self.english.id], "action": "ADD"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check the action log
        log = ActionLog.objects.filter(
            category="UPDATE",
            content_type__model="teacher",
            action="Teacher subjects add operation",
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)

        # Verify metadata
        self.assertEqual(log.metadata["action_type"], "SUBJECT_ADD")
        self.assertEqual(len(log.metadata["added_subjects"]), 2)
        self.assertEqual(len(log.metadata["current_subjects"]), 2)
        self.assertEqual(log.metadata["teacher_id"], self.teacher.id)

    def test_remove_subjects_logging(self):
        # First add some subjects
        self.teacher.subjects_taught.add(self.math, self.english)

        # Now remove one
        url = reverse("teacher-assign-subjects", args=[self.teacher.id])
        data = {"subject_ids": [self.math.id], "action": "REMOVE"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check the action log
        log = ActionLog.objects.filter(
            metadata__action_type="SUBJECT_REMOVE",
            action="Teacher subjects remove operation",
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(len(log.metadata["removed_subjects"]), 1)
        self.assertEqual(log.metadata["removed_subjects"][0], self.math.id)
        self.assertEqual(len(log.metadata["current_subjects"]), 1)

    def test_replace_subjects_logging(self):
        # First add some subjects
        self.teacher.subjects_taught.add(self.math, self.english)

        # Now replace all
        url = reverse("teacher-assign-subjects", args=[self.teacher.id])
        data = {"subject_ids": [self.science.id], "action": "REPLACE"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check the action log
        log = ActionLog.objects.filter(
            metadata__action_type="SUBJECT_REPLACE",
            action="Teacher subjects replace operation",
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(len(log.metadata["previous_subjects"]), 2)
        self.assertEqual(len(log.metadata["new_subjects"]), 1)
        self.assertEqual(log.metadata["new_subjects"][0], self.science.id)


class TeacherClassAssignmentLoggingTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        # Create test classes
        self.class1 = SchoolClass.objects.create(
            name="Form 1",
            grade_level="Form 1",
            school=self.school,
            academic_year="2023",
        )
        self.class2 = SchoolClass.objects.create(
            name="Form 2",
            grade_level="Form 2",
            school=self.school,
            academic_year="2023",
        )
        self.class3 = SchoolClass.objects.create(
            name="Form 3",
            grade_level="Form 3",
            school=self.school,
            academic_year="2023",
        )

    def test_add_classes_logging(self):
        url = reverse("teacher-assign-classes", args=[self.teacher.id])
        data = {"class_ids": [self.class1.id, self.class2.id], "action": "ADD"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check the action log
        log = ActionLog.objects.filter(
            category="UPDATE",
            content_type__model="teacher",
            action="Teacher classes add operation",
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)

        # Verify metadata
        self.assertEqual(log.metadata["action_type"], "CLASS_ADD")
        self.assertEqual(len(log.metadata["added_classes"]), 2)
        self.assertEqual(len(log.metadata["current_classes"]), 2)
        self.assertEqual(log.metadata["teacher_id"], self.teacher.id)

    def test_remove_classes_logging(self):
        # First add some classes
        self.teacher.assigned_classes.add(self.class1, self.class2)

        # Now remove one
        url = reverse("teacher-assign-classes", args=[self.teacher.id])
        data = {"class_ids": [self.class1.id], "action": "REMOVE"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check the action log
        log = ActionLog.objects.filter(
            metadata__action_type="CLASS_REMOVE",
            action="Teacher classes remove operation",
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(len(log.metadata["removed_classes"]), 1)
        self.assertEqual(log.metadata["removed_classes"][0], self.class1.id)
        self.assertEqual(len(log.metadata["current_classes"]), 1)

    def test_replace_classes_logging(self):
        # First add some classes
        self.teacher.assigned_classes.add(self.class1, self.class2)

        # Now replace all
        url = reverse("teacher-assign-classes", args=[self.teacher.id])
        data = {"class_ids": [self.class3.id], "action": "REPLACE"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check the action log
        log = ActionLog.objects.filter(
            metadata__action_type="CLASS_REPLACE",
            action="Teacher classes replace operation",
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(len(log.metadata["previous_classes"]), 2)
        self.assertEqual(len(log.metadata["new_classes"]), 1)
        self.assertEqual(log.metadata["new_classes"][0], self.class3.id)


# python manage.py test skul_data.tests.teachers_tests.test_teachers_logging
