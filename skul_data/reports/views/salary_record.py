from rest_framework import viewsets, permissions
from skul_data.reports.models.salary_record import SalaryRecord
from skul_data.reports.serializers.salary_record import SalaryRecordSerializer


class SalaryRecordViewSet(viewsets.ModelViewSet):
    """
    Viewset to manage salary records.
    - Only school admins can create and update records.
    - Anyone in the school can view them.
    """

    queryset = SalaryRecord.objects.all()
    serializer_class = SalaryRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
