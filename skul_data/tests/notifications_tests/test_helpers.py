# notifications/tests/test_helpers.py
import uuid
from django.contrib.auth import get_user_model
from django.utils import timezone
from skul_data.notifications.models.notification import (
    Notification,
    Message,
    MessageAttachment,
)

User = get_user_model()


def create_test_notification(user=None, **kwargs):
    """Helper to create notification entries for testing"""
    if user is None:
        user = User.objects.create_user(
            username=f"testuser_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass",
        )

    return Notification.objects.create(
        user=user,
        notification_type=kwargs.get("notification_type", "MESSAGE"),
        title=kwargs.get("title", "Test Notification"),
        message=kwargs.get("message", "This is a test notification"),
        is_read=kwargs.get("is_read", False),
        related_model=kwargs.get("related_model", None),
        related_id=kwargs.get("related_id", None),
        created_at=kwargs.get("created_at", timezone.now()),
    )


def create_test_message(sender=None, recipient=None, **kwargs):
    """Helper to create message entries for testing"""
    if sender is None:
        sender = User.objects.create_user(
            username=f"sender_{uuid.uuid4().hex[:8]}",
            email=f"sender_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass",
        )

    if recipient is None:
        recipient = User.objects.create_user(
            username=f"recipient_{uuid.uuid4().hex[:8]}",
            email=f"recipient_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass",
        )

    return Message.objects.create(
        sender=sender,
        recipient=recipient,
        message_type=kwargs.get("message_type", "TEACHER"),
        subject=kwargs.get("subject", "Test Message"),
        body=kwargs.get("body", "This is a test message"),
        is_read=kwargs.get("is_read", False),
        created_at=kwargs.get("created_at", timezone.now()),
    )


def create_test_attachment(message=None, **kwargs):
    """Helper to create message attachments for testing"""
    if message is None:
        sender = User.objects.create_user(
            username=f"sender_{uuid.uuid4().hex[:8]}",
            email=f"sender_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass",
        )
        recipient = User.objects.create_user(
            username=f"recipient_{uuid.uuid4().hex[:8]}",
            email=f"recipient_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass",
        )
        message = create_test_message(sender, recipient)

    return MessageAttachment.objects.create(
        message=message,
        file=kwargs.get("file", "message_attachments/test.txt"),
        original_filename=kwargs.get("original_filename", "test.txt"),
    )
