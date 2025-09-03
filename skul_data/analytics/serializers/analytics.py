from rest_framework import serializers
from skul_data.analytics.models.analytics import (
    AnalyticsDashboard,
    CachedAnalytics,
    AnalyticsAlert,
)
from skul_data.schools.serializers.school import SchoolSerializer
from skul_data.users.serializers.base_user import BaseUserSerializer
from skul_data.schools.models.school import School


class AnalyticsDashboardSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    created_by = BaseUserSerializer(read_only=True)

    class Meta:
        model = AnalyticsDashboard
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def create(self, validated_data):
        # Get school from request user if not provided
        if "school" not in validated_data:
            validated_data["school"] = self.context["request"].user.school
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


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
        # Make the validation more flexible - if no date filters are provided,
        # set a default date_range
        if not any(
            [data.get("date_range"), data.get("start_date"), data.get("end_date")]
        ):
            data["date_range"] = "last_30_days"  # Default to last 30 days

        # If start_date or end_date is provided, both should be present
        if data.get("start_date") or data.get("end_date"):
            if not (data.get("start_date") and data.get("end_date")):
                raise serializers.ValidationError(
                    "Both start_date and end_date are required when using date range filters"
                )

        return data


# from rest_framework import serializers
# from datetime import date, timedelta


# class AnalyticsFilterSerializer(serializers.Serializer):
#     """Serializer for validating analytics filters"""

#     date_range = serializers.CharField(required=False)
#     start_date = serializers.DateField(required=False)
#     end_date = serializers.DateField(required=False)
#     class_id = serializers.IntegerField(required=False)
#     user_type = serializers.CharField(required=False)
#     performance_threshold = serializers.IntegerField(required=False)
#     category = serializers.CharField(required=False)

#     def validate(self, data):
#         # If no date parameters are provided, set default to last 30 days
#         if (
#             not data.get("date_range")
#             and not data.get("start_date")
#             and not data.get("end_date")
#         ):
#             data["date_range"] = "30_days"

#         # If date_range is provided, validate it
#         if data.get("date_range"):
#             valid_ranges = ["7_days", "30_days", "90_days", "365_days", "all_time"]
#             if data["date_range"] not in valid_ranges:
#                 raise serializers.ValidationError(
#                     f"date_range must be one of: {', '.join(valid_ranges)}"
#                 )

#         # If start_date is provided without end_date, set end_date to today
#         if data.get("start_date") and not data.get("end_date"):
#             data["end_date"] = date.today()

#         # If end_date is provided without start_date, set start_date to 30 days ago
#         if data.get("end_date") and not data.get("start_date"):
#             data["start_date"] = data["end_date"] - timedelta(days=30)

#         # Validate date range if both dates are provided
#         if data.get("start_date") and data.get("end_date"):
#             if data["start_date"] > data["end_date"]:
#                 raise serializers.ValidationError("start_date cannot be after end_date")

#         return data

#     def to_internal_value(self, data):
#         """Convert date_range to actual dates"""
#         validated_data = super().to_internal_value(data)

#         if validated_data.get("date_range"):
#             end_date = date.today()
#             range_mapping = {
#                 "7_days": 7,
#                 "30_days": 30,
#                 "90_days": 90,
#                 "365_days": 365,
#                 "all_time": None,
#             }

#             days = range_mapping.get(validated_data["date_range"])
#             if days is not None:
#                 start_date = end_date - timedelta(days=days)
#                 validated_data["start_date"] = start_date
#                 validated_data["end_date"] = end_date
#             else:  # all_time
#                 validated_data["start_date"] = None
#                 validated_data["end_date"] = None

#         return validated_data
