from rest_framework import serializers
from skul_data.notifications.models.notification import (
    Notification,
    Message,
    MessageAttachment,
)
from skul_data.users.serializers.base_user import UserDetailSerializer
from skul_data.users.models.base_user import User


from rest_framework import serializers
from skul_data.notifications.models.notification import (
    Notification,
    Message,
    MessageAttachment,
)
from skul_data.users.serializers.base_user import UserDetailSerializer
from skul_data.users.models.base_user import User


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ["id", "file", "original_filename", "uploaded_at"]


class MessageSerializer(serializers.ModelSerializer):
    sender = UserDetailSerializer(read_only=True)
    recipient = serializers.SerializerMethodField()
    recipient_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), write_only=True, source="recipient"
    )
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    sender_name = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "recipient",
            "recipient_id",
            "message_type",
            "subject",
            "body",
            "is_read",
            "created_at",
            "attachments",
            "sender_name",
            "recipient_name",
        ]

    def get_recipient(self, obj):
        """Return recipient details for read operations"""
        if obj.recipient:
            return {
                "id": obj.recipient.id,
                "first_name": obj.recipient.first_name,
                "last_name": obj.recipient.last_name,
                "email": obj.recipient.email,
                "user_type": obj.recipient.user_type,
            }
        return None

    def get_sender_name(self, obj):
        """Get sender's full name"""
        if obj.sender:
            return obj.sender.get_full_name()
        return "System"

    def get_recipient_name(self, obj):
        """Get recipient's full name"""
        if obj.recipient:
            return obj.recipient.get_full_name()
        return "Unknown"


class MessageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for message lists"""

    sender_name = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender_name",
            "recipient_name",
            "message_type",
            "subject",
            "is_read",
            "created_at",
            "attachment_count",
        ]

    def get_sender_name(self, obj):
        if obj.sender:
            return obj.sender.get_full_name()
        return "System"

    def get_recipient_name(self, obj):
        if obj.recipient:
            return obj.recipient.get_full_name()
        return "Unknown"

    def get_attachment_count(self, obj):
        return obj.attachments.count()


class MessageRecipientSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="user_type")
    type_display = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "type",
            "type_display",
            "full_name",
        ]

    def get_type_display(self, obj):
        return obj.get_user_type_display()

    def get_full_name(self, obj):
        return obj.get_full_name()


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
