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
    # recipient = UserDetailSerializer(read_only=True)
    recipient = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
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


class MessageRecipientSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="user_type")
    type_display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "type", "type_display"]

    def get_type(self, obj):
        return obj.user_type

    def get_type_display(self, obj):
        return obj.get_user_type_display()


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
