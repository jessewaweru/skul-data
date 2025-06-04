from django.test import TransactionTestCase
from django.utils import timezone
from datetime import timedelta
from skul_data.users.models import User
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.action_logs.utils.action_log import log_action
from skul_data.students.models.student import Student
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_document,
)
from django.contrib.contenttypes.models import ContentType
from skul_data.documents.models.document import DocumentShareLink, Document
from skul_data.users.models.role import Role, Permission
from django.db import transaction


class ActionLogSignalsTest(TransactionTestCase):
    """Test action log signals with proper isolation"""

    def setUp(self):
        """Set up test data with proper transaction management"""
        # Clear all existing action logs to start fresh
        ActionLog.objects.all().delete()

        # Temporarily disable signals during setup to avoid interference
        from django.db import transaction

        with transaction.atomic():
            self.school, self.admin_user = create_test_school()
            # Ensure the user is properly saved and committed
            self.admin_user.refresh_from_db()

        # Set the current user for logging
        User.set_current_user(self.admin_user)

    def tearDown(self):
        """Clean up after each test"""
        User.set_current_user(None)
        ActionLog.objects.all().delete()

    def test_log_model_save_create(self):
        """Test that model creation is logged correctly"""
        # Clear any existing logs
        ActionLog.objects.all().delete()

        # Create student and explicitly set current user
        student = create_test_student(self.school)
        student._current_user = self.admin_user
        student.save()  # Trigger the signal again with current user set

        # Wait for transaction to complete
        transaction.get_connection().ensure_connection()

        logs = ActionLog.objects.filter(
            category=ActionCategory.CREATE, action=f"Created {Student.__name__}"
        )

        self.assertEqual(logs.count(), 1, f"Expected 1 CREATE log, got {logs.count()}")
        log = logs.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.content_object, student)

    def test_log_model_save_update(self):
        """Test that model updates are logged correctly"""
        # Clear existing logs
        ActionLog.objects.all().delete()

        # Create student first
        student = create_test_student(self.school)
        student._current_user = self.admin_user
        student.save()

        # Clear logs to focus on update
        ActionLog.objects.all().delete()

        # Now update the student
        student.first_name = "Updated"
        student._current_user = self.admin_user
        student._changed_fields = ["first_name"]  # Track the change
        student.save()

        logs = ActionLog.objects.filter(
            category=ActionCategory.UPDATE, action=f"Updated {Student.__name__}"
        )

        self.assertEqual(logs.count(), 1, f"Expected 1 UPDATE log, got {logs.count()}")
        log = logs.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.content_object, student)
        self.assertIn("fields_changed", log.metadata)

    def test_log_model_delete(self):
        """Test that model deletion is logged correctly"""
        # Clear existing logs
        ActionLog.objects.all().delete()

        student = create_test_student(self.school)
        student._current_user = self.admin_user
        student_id = student.id
        student.delete()

        logs = ActionLog.objects.filter(
            category=ActionCategory.DELETE, action=f"Deleted {Student.__name__}"
        )

        self.assertEqual(logs.count(), 1, f"Expected 1 DELETE log, got {logs.count()}")
        log = logs.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.object_id, student_id)

    def test_no_log_for_action_log_model(self):
        """Test that ActionLog model changes don't create recursive logs"""
        # Clear all existing logs first
        ActionLog.objects.all().delete()

        # Create an ActionLog directly - this should NOT trigger a signal
        log = ActionLog.objects.create(
            user=self.admin_user, action="Test", category=ActionCategory.OTHER
        )

        # Update the log - this should also NOT trigger a signal
        log.action = "Updated"
        log.save()

        # Check that we only have the 1 log we created manually
        total_logs = ActionLog.objects.count()
        self.assertEqual(
            total_logs,
            1,
            f"Expected exactly 1 ActionLog (the one we created manually), "
            f"but found {total_logs}. ActionLog changes should not be logged.",
        )


class EnhancedActionLogSignalsTest(TransactionTestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.document = create_test_document(self.school, self.admin_user)
        # Set current user for the test session
        User.set_current_user(self.admin_user)

    def test_share_link_creation_signal(self):
        """Test that share link creation triggers action log"""
        expires_at = timezone.now() + timedelta(days=7)  # Use shorter timeframe

        # Create share link with explicit user assignment
        share_link = DocumentShareLink.objects.create(
            document=self.document,
            created_by=self.admin_user,
            expires_at=expires_at,
            download_limit=5,
        )

        # Manually set current user and save to trigger update signal if needed
        share_link._current_user = self.admin_user

        # Check that the share link creation was logged
        logs = ActionLog.objects.filter(
            category=ActionCategory.SHARE,
            content_type=ContentType.objects.get_for_model(DocumentShareLink),
            object_id=share_link.id,
        )

        print(f"Found {logs.count()} share link logs")
        for log in logs:
            print(
                f"Log: {log.action}, Category: {log.category}, Metadata: {log.metadata}"
            )

        self.assertEqual(
            logs.count(), 1, "Expected exactly one share link creation log"
        )

        log = logs.first()
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.content_object, share_link)
        self.assertEqual(log.metadata["document_id"], self.document.id)
        self.assertIsNotNone(log.metadata["expires_at"])
        self.assertFalse(log.metadata["has_password"])

    def test_password_protected_share_link(self):
        """Test password-protected share link logging"""
        expires_at = timezone.now() + timedelta(days=7)

        share_link = DocumentShareLink.objects.create(
            document=self.document,
            created_by=self.admin_user,
            expires_at=expires_at,
            download_limit=5,
            password="secret",
        )
        share_link._current_user = self.admin_user

        log = ActionLog.objects.filter(
            category=ActionCategory.SHARE, object_id=share_link.id
        ).first()

        self.assertIsNotNone(log, "Share link creation should be logged")
        self.assertTrue(log.metadata["has_password"])

    def test_document_operations_with_metadata(self):
        """Test that document operations include proper metadata"""
        # Set current user before making changes
        self.document._current_user = self.admin_user
        self.document.title = "Updated Title"
        self.document._changed_fields = ["title"]  # Simulate model tracking
        self.document.save()

        log = ActionLog.objects.filter(
            category=ActionCategory.UPDATE,
            content_type=ContentType.objects.get_for_model(Document),
            object_id=self.document.id,
        ).first()

        self.assertIsNotNone(log, "Document update should be logged")
        self.assertIn("fields_changed", log.metadata)
        self.assertEqual(log.metadata["fields_changed"], ["title"])
        self.assertEqual(log.metadata["new_values"]["title"], "Updated Title")

    def test_share_link_download_count_increment(self):
        """Test that download count increments are logged"""
        doc = create_test_document(self.school, self.admin_user)
        share_link = DocumentShareLink.objects.create(
            document=doc,
            created_by=self.admin_user,
            expires_at=timezone.now() + timedelta(days=7),
            download_limit=3,
        )

        # Simulate download by incrementing count
        share_link.download_count += 1
        share_link._current_user = self.admin_user
        share_link._changed_fields = ["download_count"]  # Track the change
        share_link._download_increment = True  # Flag for download action
        share_link.save()

        # Check that the download was logged
        log = ActionLog.objects.filter(
            category=ActionCategory.DOWNLOAD, object_id=share_link.id
        ).first()

        self.assertIsNotNone(log, "Download should be logged")
        self.assertEqual(log.metadata["download_count"], 1)
        self.assertEqual(log.category, ActionCategory.DOWNLOAD)
        self.assertTrue(log.metadata.get("via_share_link", False))

    def test_password_protected_share_link_attempts(self):
        """Test password attempt logging"""
        doc = create_test_document(self.school, self.admin_user)
        share_link = DocumentShareLink.objects.create(
            document=doc,
            created_by=self.admin_user,
            password="secret123",
            expires_at=timezone.now() + timedelta(days=1),
        )

        # Simulate failed password attempt
        log_action(
            user=None,
            action="Failed password attempt",
            category=ActionCategory.OTHER,
            obj=share_link,
            metadata={"ip_address": "192.168.1.1", "attempted_password": "wrongpass"},
        )

        log = ActionLog.objects.filter(action="Failed password attempt").first()

        self.assertIsNotNone(log, "Failed password attempt should be logged")
        self.assertEqual(log.action, "Failed password attempt")
        self.assertEqual(log.metadata["attempted_password"], "wrongpass")
        self.assertEqual(log.metadata["ip_address"], "192.168.1.1")

    def tearDown(self):
        from django.db import connections

        # 1. Close all connections
        for conn in connections.all():
            conn.close()

        # 2. Additional cleanup for PostgreSQL
        if "postgresql" in connections["default"].settings_dict["ENGINE"]:
            with connections["default"].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = current_database()
                    AND pid <> pg_backend_pid();
                """
                )

        # 3. Clear your application state
        User.set_current_user(None)
        ActionLog.objects.all().delete()

        # 4. Force garbage collection to clean up any lingering references
        import gc

        gc.collect()


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_signals
