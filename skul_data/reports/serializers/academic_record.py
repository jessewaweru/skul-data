from rest_framework import serializers
from skul_data.reports.models.academic_record import AcademicRecord, TeacherComment
from decimal import Decimal


class AcademicRecordSerializer(serializers.ModelSerializer):
    performance_assessment = serializers.CharField(read_only=True)

    class Meta:
        model = AcademicRecord
        fields = "__all__"
        read_only_fields = ("grade", "created_at", "updated_at")

    def validate_score(self, value):
        if value < Decimal("0") or value > Decimal("100"):
            raise serializers.ValidationError("Score must be between 0 and 100")
        return value


class TeacherCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherComment
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
