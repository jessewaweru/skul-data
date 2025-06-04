import uuid
import time
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.action_logs.utils.action_log import log_action
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_document,
)

from skul_data.action_logs.utils.action_log import (
    log_action_async,
    log_system_action,
    set_test_mode,
)
from skul_data.documents.models.document import DocumentShareLink


class LogActionUtilityTest(TestCase):
    def setUp(self):
        print(f"[DEBUG] Test setUp started")
        self.school, self.admin_user = create_test_school()
        # Enable test mode for action logging
        set_test_mode(True)
        # Clear any action logs created during setup
        ActionLog.objects.all().delete()
        print(
            f"[DEBUG] Test setUp completed, ActionLog count: {ActionLog.objects.count()}"
        )

    def tearDown(self):
        print(f"[DEBUG] Test tearDown started")
        # Disable test mode after tests
        set_test_mode(False)
        print(f"[DEBUG] Test tearDown completed")

    def test_log_action_with_object(self):
        # Clear any existing logs
        ActionLog.objects.all().delete()

        student = create_test_student(self.school)
        # Clear logs created by student creation
        ActionLog.objects.all().delete()

        log_action(
            user=self.admin_user,
            action="Test action",
            category=ActionCategory.OTHER,
            obj=student,
        )

        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.action, "Test action")
        self.assertEqual(log.category, ActionCategory.OTHER)
        self.assertEqual(log.content_object, student)

    def test_log_action_without_object(self):
        # Clear any existing logs
        ActionLog.objects.all().delete()

        log_action(
            user=self.admin_user, action="System action", category=ActionCategory.SYSTEM
        )

        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.action, "System action")
        self.assertEqual(log.category, ActionCategory.SYSTEM)
        self.assertIsNone(log.content_object)

    def test_log_action_with_metadata(self):
        # Clear any existing logs
        ActionLog.objects.all().delete()

        metadata = {"key": "value", "count": 42}

        log_action(
            user=self.admin_user,
            action="Action with metadata",
            category=ActionCategory.OTHER,
            metadata=metadata,
        )

        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertEqual(log.metadata, metadata)

    def test_log_action_without_user(self):
        # Clear any existing logs
        ActionLog.objects.all().delete()

        system_tag = uuid.UUID("00000000-0000-0000-0000-000000000000")
        log_action(user=None, action="Anonymous action", category=ActionCategory.OTHER)

        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertIsNone(log.user)
        self.assertEqual(log.action, "Anonymous action")
        self.assertEqual(log.user_tag, system_tag)

    def test_log_action_async_in_transaction(self):
        print(f"\n[DEBUG] === test_log_action_async_in_transaction started ===")

        # Clear any existing logs at the start
        ActionLog.objects.all().delete()

        student = create_test_student(self.school)
        # Clear logs created by student creation, but count them first
        logs_after_student = ActionLog.objects.count()
        ActionLog.objects.all().delete()

        print(
            f"[DEBUG] Student created, cleared {logs_after_student} logs, current count: {ActionLog.objects.count()}"
        )

        with transaction.atomic():
            print(f"[DEBUG] Entering transaction.atomic() block")
            log_action_async(
                user=self.admin_user,
                action="Async test action",
                category=ActionCategory.OTHER,
                obj=student,
            )
            print(
                f"[DEBUG] log_action_async called, ActionLog count inside transaction: {ActionLog.objects.count()}"
            )

        print(
            f"[DEBUG] Transaction block exited, ActionLog count: {ActionLog.objects.count()}"
        )

        # After transaction commits - should have exactly 1 log
        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertEqual(log.action, "Async test action")
        self.assertEqual(log.content_object, student)
        print(f"[DEBUG] === test_log_action_async_in_transaction completed ===\n")

    def test_log_action_async_no_transaction(self):
        print(f"\n[DEBUG] === test_log_action_async_no_transaction started ===")

        # Clear any existing logs at the start
        ActionLog.objects.all().delete()

        student = create_test_student(self.school)
        # Clear logs created by student creation
        logs_after_student = ActionLog.objects.count()
        ActionLog.objects.all().delete()

        print(
            f"[DEBUG] Student created, cleared {logs_after_student} logs, current count: {ActionLog.objects.count()}"
        )

        # Outside transaction - should create immediately in test mode
        log_action_async(
            user=self.admin_user,
            action="Async immediate action",
            category=ActionCategory.OTHER,
            obj=student,
        )

        print(
            f"[DEBUG] log_action_async called, ActionLog count: {ActionLog.objects.count()}"
        )

        # In test mode, this should be created immediately (synchronously)
        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertEqual(log.action, "Async immediate action")
        print(f"[DEBUG] === test_log_action_async_no_transaction completed ===\n")

    def test_log_system_action(self):
        # Clear any existing logs
        ActionLog.objects.all().delete()

        log_system_action(
            action="System maintenance",
            category=ActionCategory.SYSTEM,
            metadata={"operation": "database cleanup"},
        )

        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertIsNone(log.user)
        self.assertEqual(log.action, "System maintenance")
        self.assertTrue(log.metadata["system_operation"])
        self.assertEqual(log.metadata["operation"], "database cleanup")

    def test_log_action_with_complex_metadata(self):
        # Clear any existing logs
        ActionLog.objects.all().delete()

        student = create_test_student(self.school)
        # Clear logs created by student creation
        ActionLog.objects.all().delete()

        complex_metadata = {
            "nested": {
                "key": "value",
                "list": [1, 2, 3],
                "model_ref": student,  # Model instance
            }
        }

        log_action(
            user=self.admin_user,
            action="Complex metadata test",
            category=ActionCategory.OTHER,
            metadata=complex_metadata,
        )

        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertIsInstance(log.metadata["nested"], dict)
        self.assertEqual(log.metadata["nested"]["key"], "value")
        self.assertEqual(log.metadata["nested"]["list"], [1, 2, 3])
        # Model instance should be serialized
        self.assertEqual(log.metadata["nested"]["model_ref"]["model"], "Student")
        self.assertEqual(log.metadata["nested"]["model_ref"]["id"], student.id)

    def test_log_action_with_document_share_link(self):
        # Clear any existing logs
        ActionLog.objects.all().delete()

        doc = create_test_document(self.school, self.admin_user)
        # Clear logs created by document creation
        ActionLog.objects.all().delete()

        share_link = DocumentShareLink.objects.create(
            document=doc,
            created_by=self.admin_user,
            expires_at=timezone.now() + timedelta(days=7),
        )
        # Clear logs created by share link creation (from signals)
        ActionLog.objects.all().delete()

        log_action(
            user=self.admin_user,
            action="Created share link",
            category=ActionCategory.SHARE,
            obj=share_link,
            metadata={"document_id": doc.id, "expires_in_days": 7},
        )

        self.assertEqual(ActionLog.objects.count(), 1)
        log = ActionLog.objects.first()
        self.assertEqual(log.content_object, share_link)
        self.assertEqual(log.metadata["document_id"], doc.id)
        self.assertEqual(log.metadata["expires_in_days"], 7)


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_utils
