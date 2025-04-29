from rest_framework import serializers
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.users.serializers.base_user import BaseUserSerializer


class ActionLogSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()
    affected_model = serializers.SerializerMethodField()
    affected_object = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()

    class Meta:
        model = ActionLog
        fields = [
            "id",
            "user",
            "user_details",
            "user_tag",
            "action",
            "category",
            "category_display",
            "ip_address",
            "user_agent",
            "content_type",
            "object_id",
            "affected_model",
            "affected_object",
            "metadata",
            "timestamp",
        ]
        read_only_fields = fields

    def get_user_details(self, obj):
        if obj.user:
            return BaseUserSerializer(obj.user).data
        return None

    def get_affected_model(self, obj):
        return obj.affected_model

    def get_affected_object(self, obj):
        return obj.affected_object

    def get_category_display(self, obj):
        return obj.get_category_display()
