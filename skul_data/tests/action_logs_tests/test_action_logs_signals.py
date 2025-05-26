from django.test import TransactionTestCase
from skul_data.users.models import User
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.students.models.student import Student
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_school,
    create_test_student,
)


class ActionLogSignalsTest(TransactionTestCase):
    def setUp(self):
        # Temporarily disable signals during setup to avoid circular dependency
        from django.db import transaction

        with transaction.atomic():
            self.school, self.admin_user = create_test_school()
            # Ensure the user is properly saved and committed
            self.admin_user.refresh_from_db()

        # Now set the current user for logging
        User.set_current_user(self.admin_user)

    def test_log_model_save_create(self):
        # Create student and explicitly set current user
        student = create_test_student(self.school)
        student._current_user = self.admin_user  # Explicitly set current user
        student.save()  # Trigger the signal again with current user set

        logs = ActionLog.objects.filter(
            category=ActionCategory.CREATE, action=f"Created {Student.__name__}"
        )

        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.content_object, student)

    def test_log_model_save_update(self):
        # Create student first
        student = create_test_student(self.school)
        student._current_user = self.admin_user
        student.save()  # This should create a CREATE log

        # Clear existing logs to focus on update
        ActionLog.objects.all().delete()

        # Now update the student
        student.first_name = "Updated"
        student._current_user = self.admin_user  # Set current user for update
        student.save()

        logs = ActionLog.objects.filter(
            category=ActionCategory.UPDATE, action=f"Updated {Student.__name__}"
        )

        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.content_object, student)
        self.assertIn("fields_changed", log.metadata)
        self.assertIn("new_values", log.metadata)

    def test_log_model_delete(self):
        student = create_test_student(self.school)
        student._current_user = self.admin_user  # Set current user on instance
        student_id = student.id
        student.delete()

        logs = ActionLog.objects.filter(
            category=ActionCategory.DELETE, action=f"Deleted {Student.__name__}"
        )

        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.object_id, student_id)

    def test_no_log_for_action_log_model(self):
        # Shouldn't log changes to ActionLog itself
        log = ActionLog.objects.create(
            user=self.admin_user, action="Test", category=ActionCategory.OTHER
        )

        log.action = "Updated"
        log.save()

        # Check no new logs were created for the update
        self.assertEqual(ActionLog.objects.count(), 1)


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_signals
