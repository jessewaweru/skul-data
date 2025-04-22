from rest_framework import serializers
from skul_data.schools.models.schoolstream import SchoolStream


class SchoolStreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolStream
        fields = ["id", "name", "description", "created_at"]
        read_only_fields = ["created_at"]


class SchoolStreamCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolStream
        fields = ["name", "description"]

    def validate_name(self, value):
        """Ensure uniqueness only within the same school"""
        school = self.context["request"].user.school
        if SchoolStream.objects.filter(
            school=school, name__iexact=value.strip()
        ).exists():
            raise serializers.ValidationError(
                "Your school already has a stream with this name"
            )
        return value.strip()
