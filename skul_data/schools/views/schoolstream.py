from rest_framework import viewsets
from skul_data.schools.models.schoolstream import SchoolStream
from skul_data.schools.serializers.schoolstream import (
    SchoolStreamSerializer,
    SchoolStreamCreateSerializer,
)
from skul_data.users.permissions.permission import IsAdministrator
from skul_data.users.models.base_user import User


class SchoolStreamViewSet(viewsets.ModelViewSet):
    """Endpoint that allows school streams to be viewed or edited."""

    serializer_class = SchoolStreamSerializer
    permission_classes = [IsAdministrator]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SchoolStreamCreateSerializer
        return SchoolStreamSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return SchoolStream.objects.all()

        school = getattr(user, "school", None)
        if not school:
            return SchoolStream.objects.none()

        return SchoolStream.objects.filter(school=school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)
