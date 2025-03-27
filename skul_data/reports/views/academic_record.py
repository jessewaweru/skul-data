from rest_framework import viewsets, permissions
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.reports.serializers.academic_record import AcademicRecordSerializer


class AcademicRecordViewSet(viewsets.ModelViewSet):
    """
    Viewset to manage academic records.
    - Teachers can create and update records.
    - Anyone can retrieve them.
    """

    queryset = AcademicRecord.objects.all()
    serializer_class = AcademicRecordSerializer
    permission_classes = [permissions.IsAuthenticated]  # Modify as needed

    def perform_create(self, serializer):
        serializer.save(teacher=self.request.user.teacher)
