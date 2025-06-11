# notifications/tests/test_serializers.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from skul_data.notifications.serializers.notification import (
    NotificationSerializer,
    MessageSerializer,
    MessageAttachmentSerializer,
    MessageRecipientSerializer,
)
from .test_helpers import (
    create_test_notification,
    create_test_message,
    create_test_attachment,
)

User = get_user_model()


class NotificationSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )
        self.notification = create_test_notification(user=self.user)
        self.serializer = NotificationSerializer(instance=self.notification)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "notification_type",
                "title",
                "message",
                "is_read",
                "related_model",
                "related_id",
                "created_at",
            },
        )

    def test_field_content(self):
        data = self.serializer.data
        self.assertEqual(data["notification_type"], "MESSAGE")
        self.assertEqual(data["title"], "Test Notification")
        self.assertEqual(data["message"], "This is a test notification")
        self.assertFalse(data["is_read"])


class MessageSerializerTest(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="sender", email="sender@example.com", password="testpass"
        )
        self.recipient = User.objects.create_user(
            username="recipient", email="recipient@example.com", password="testpass"
        )
        self.message = create_test_message(sender=self.sender, recipient=self.recipient)
        self.serializer = MessageSerializer(instance=self.message)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "sender",
                "recipient",
                "message_type",
                "subject",
                "body",
                "is_read",
                "created_at",
                "attachments",
            },
        )

    def test_field_content(self):
        data = self.serializer.data
        self.assertEqual(data["message_type"], "TEACHER")
        self.assertEqual(data["subject"], "Test Message")
        self.assertEqual(data["body"], "This is a test message")
        self.assertFalse(data["is_read"])
        self.assertEqual(len(data["attachments"]), 0)


class MessageAttachmentSerializerTest(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="sender", email="sender@example.com", password="testpass"
        )
        self.recipient = User.objects.create_user(
            username="recipient", email="recipient@example.com", password="testpass"
        )
        self.message = create_test_message(sender=self.sender, recipient=self.recipient)
        self.attachment = create_test_attachment(message=self.message)
        self.serializer = MessageAttachmentSerializer(instance=self.attachment)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()), {"id", "file", "original_filename", "uploaded_at"}
        )

    def test_field_content(self):
        data = self.serializer.data
        self.assertEqual(data["file"], "/message_attachments/test.txt")
        self.assertEqual(data["original_filename"], "test.txt")


class MessageRecipientSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            user_type="teacher",
        )
        self.serializer = MessageRecipientSerializer(instance=self.user)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {"id", "first_name", "last_name", "email", "type", "type_display"},
        )

    def test_field_content(self):
        data = self.serializer.data
        self.assertEqual(data["type"], "teacher")
        self.assertEqual(data["type_display"], "Teacher")


# python manage.py test skul_data.tests.notifications_tests.test_notifications_serializers
