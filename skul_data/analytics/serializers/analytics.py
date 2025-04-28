from rest_framework import serializers
from skul_data.analytics.models.analytics import (
    AnalyticsDashboard,
    CachedAnalytics,
    AnalyticsAlert,
)
from skul_data.schools.serializers.school import SchoolSerializer
from skul_data.users.serializers.base_user import BaseUserSerializer


class AnalyticsDashboardSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    created_by = BaseUserSerializer(read_only=True)

    class Meta:
        model = AnalyticsDashboard
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class CachedAnalyticsSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)

    class Meta:
        model = CachedAnalytics
        fields = "__all__"
        read_only_fields = ("computed_at",)


class AnalyticsAlertSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)

    class Meta:
        model = AnalyticsAlert
        fields = "__all__"
        read_only_fields = ("created_at", "resolved_at")


class AnalyticsFilterSerializer(serializers.Serializer):
    """Serializer for validating analytics filters"""

    date_range = serializers.CharField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    class_id = serializers.IntegerField(required=False)
    user_type = serializers.CharField(required=False)
    performance_threshold = serializers.IntegerField(required=False)
    category = serializers.CharField(required=False)

    def validate(self, data):
        if "date_range" not in data and (
            "start_date" not in data or "end_date" not in data
        ):
            raise serializers.ValidationError(
                "Either date_range or both start_date and end_date are required"
            )
        return data
