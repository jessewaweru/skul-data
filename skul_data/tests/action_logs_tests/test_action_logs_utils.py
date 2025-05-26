from django.test import TestCase
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.action_logs.utils.action_log import log_action
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_school,
    create_test_student,
)
import uuid


class LogActionUtilityTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()

    def test_log_action_with_object(self):
        student = create_test_student(self.school)

        log_action(
            user=self.admin_user,
            action="Test action",
            category=ActionCategory.OTHER,
            obj=student,
        )

        log = ActionLog.objects.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.action, "Test action")
        self.assertEqual(log.category, ActionCategory.OTHER)
        self.assertEqual(log.content_object, student)

    def test_log_action_without_object(self):
        log_action(
            user=self.admin_user, action="System action", category=ActionCategory.SYSTEM
        )

        log = ActionLog.objects.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.action, "System action")
        self.assertEqual(log.category, ActionCategory.SYSTEM)
        self.assertIsNone(log.content_object)

    def test_log_action_with_metadata(self):
        metadata = {"key": "value", "count": 42}

        log_action(
            user=self.admin_user,
            action="Action with metadata",
            category=ActionCategory.OTHER,
            metadata=metadata,
        )

        log = ActionLog.objects.first()
        self.assertEqual(log.metadata, metadata)

    def test_log_action_without_user(self):
        system_tag = uuid.UUID("00000000-0000-0000-0000-000000000000")
        log_action(user=None, action="Anonymous action", category=ActionCategory.OTHER)

        log = ActionLog.objects.first()
        self.assertIsNone(log.user)
        self.assertEqual(log.action, "Anonymous action")
        self.assertEqual(log.user_tag, system_tag)


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_utils
