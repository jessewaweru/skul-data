from django.db import models
from django.conf import settings


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("SYSTEM", "System Notification"),
        ("MESSAGE", "New Message"),
        ("EVENT", "Event Reminder"),
        ("REPORT", "Report Available"),
        ("DOCUMENT", "Document Shared"),
        ("PAYMENT", "Payment Notification"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_model = models.CharField(max_length=50, null=True, blank=True)
    related_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.user}"


class Message(models.Model):
    MESSAGE_TYPES = [
        ("ADMIN", "Administrative"),
        ("TEACHER", "Teacher Communication"),
        ("PARENT", "Parent Communication"),
        ("SYSTEM", "System Generated"),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} - {self.sender} to {self.recipient}"


class MessageAttachment(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="message_attachments/%Y/%m/%d/")
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.message}"
