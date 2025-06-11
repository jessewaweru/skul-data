# notifications/tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from skul_data.tests.notifications_tests.test_helpers import (
    create_test_notification,
    create_test_message,
    create_test_attachment,
)
from skul_data.notifications.models.notification import Notification, Message

User = get_user_model()


class NotificationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

    def test_notification_creation(self):
        notification = create_test_notification(user=self.user)
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.notification_type, "MESSAGE")
        self.assertEqual(notification.title, "Test Notification")
        self.assertFalse(notification.is_read)
        self.assertIsNotNone(notification.created_at)

    def test_notification_str(self):
        notification = create_test_notification(user=self.user)
        expected_str = f"New Message for {self.user}"
        self.assertEqual(str(notification), expected_str)

        notification1 = create_test_notification(
            user=self.user, created_at=timezone.now() - timedelta(days=1)
        )
        notification2 = create_test_notification(user=self.user)

        notifications = Notification.objects.all()
        self.assertEqual(notifications[0], notification2)
        self.assertEqual(notifications[1], notification1)
        self.assertEqual(notifications[0], notification2)
        self.assertEqual(notifications[1], notification1)


class MessageModelTest(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="sender", email="sender@example.com", password="testpass"
        )
        self.recipient = User.objects.create_user(
            username="recipient", email="recipient@example.com", password="testpass"
        )

    def test_message_creation(self):
        message = create_test_message(sender=self.sender, recipient=self.recipient)
        self.assertEqual(message.sender, self.sender)
        self.assertEqual(message.recipient, self.recipient)
        self.assertEqual(message.message_type, "TEACHER")
        self.assertEqual(message.subject, "Test Message")
        self.assertFalse(message.is_read)
        self.assertIsNotNone(message.created_at)

    def test_message_str(self):
        message = create_test_message(sender=self.sender, recipient=self.recipient)
        expected_str = "Test Message - sender to recipient"
        self.assertEqual(str(message), expected_str)

    def test_message_ordering(self):
        message1 = create_test_message(
            sender=self.sender,
            recipient=self.recipient,
            created_at=timezone.now() - timedelta(days=1),
        )
        message2 = create_test_message(sender=self.sender, recipient=self.recipient)

        messages = Message.objects.all()
        self.assertEqual(messages[0], message2)
        self.assertEqual(messages[1], message1)


class MessageAttachmentModelTest(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="sender", email="sender@example.com", password="testpass"
        )
        self.recipient = User.objects.create_user(
            username="recipient", email="recipient@example.com", password="testpass"
        )
        self.message = create_test_message(sender=self.sender, recipient=self.recipient)

    def test_attachment_creation(self):
        attachment = create_test_attachment(message=self.message)
        self.assertEqual(attachment.message, self.message)
        self.assertEqual(attachment.file, "message_attachments/test.txt")
        self.assertEqual(attachment.original_filename, "test.txt")
        self.assertIsNotNone(attachment.uploaded_at)

    def test_attachment_str(self):
        attachment = create_test_attachment(message=self.message)
        expected_str = f"Attachment for {self.message}"
        self.assertEqual(str(attachment), expected_str)


# python manage.py test skul_data.tests.notifications_tests.test_notifications_models
