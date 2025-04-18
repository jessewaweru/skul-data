from rest_framework import serializers
from skul_data.reports.models.academic_record import AcademicRecord, TeacherComment


class AcademicRecordSerializer(serializers.ModelSerializer):
    performance_assessment = serializers.CharField(read_only=True)

    class Meta:
        model = AcademicRecord
        fields = "__all__"
        read_only_fields = ("grade", "created_at", "updated_at")


class TeacherCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherComment
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
