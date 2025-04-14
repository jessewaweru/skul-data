from rest_framework import serializers
from django.utils import timezone
from skul_data.users.models.session import UserSession
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSessionSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    session_key = serializers.CharField(source="session.session_key")
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "session_key",
            "user",
            "ip_address",
            "device",
            "browser",
            "os",
            "location",
            "login_time",
            "last_activity",
            "is_active",
        ]

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "name": obj.user.get_full_name(),
            "email": obj.user.email,
            "role": (
                obj.user.role.name
                if hasattr(obj.user, "role") and obj.user.role
                else None
            ),
            "avatar": getattr(obj.user, "avatar_url", None),
        }

    def get_is_active(self, obj):
        return obj.session.expire_date > timezone.now()
