from rest_framework import serializers
from skul_data.reports.models.salary_record import SalaryRecord


class SalaryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryRecord
        fields = "__all__"
