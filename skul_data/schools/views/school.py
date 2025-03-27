from rest_framework import viewsets, permissions
from skul_data.schools.serializers.school import SchoolSerializer
from skul_data.schools.models.school import School


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
