from rest_framework import serializers
from skul_data.reports.models.academic_record import AcademicRecord


class AcademicRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicRecord
        fields = "__all__"
