from rest_framework import serializers
from skul_data.notifications.models.notification import (
    Notification,
    Message,
    MessageAttachment,
)
from skul_data.users.serializers.base_user import UserDetailSerializer


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ["id", "file", "original_filename", "uploaded_at"]


class MessageSerializer(serializers.ModelSerializer):
    sender = UserDetailSerializer(read_only=True)
    recipient = UserDetailSerializer(read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "recipient",
            "message_type",
            "subject",
            "body",
            "is_read",
            "created_at",
            "attachments",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "is_read",
            "related_model",
            "related_id",
            "created_at",
        ]
