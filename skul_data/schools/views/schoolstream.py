from rest_framework import viewsets
from skul_data.schools.models.schoolstream import SchoolStream
from skul_data.schools.serializers.schoolstream import (
    SchoolStreamSerializer,
    SchoolStreamCreateSerializer,
)
from skul_data.users.permissions.permission import IsAdministrator
from skul_data.users.models.base_user import User
from skul_data.users.permissions.permission import HasRolePermission


class SchoolStreamViewSet(viewsets.ModelViewSet):
    """Endpoint that allows school streams to be viewed or edited."""

    serializer_class = SchoolStreamSerializer
    permission_classes = [IsAdministrator | HasRolePermission]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SchoolStreamCreateSerializer
        return SchoolStreamSerializer

    def get_queryset(self):
        user = self.request.user

        # Get the user's school
        school = None
        if user.user_type == User.SCHOOL_ADMIN:
            try:
                school = user.schooladmin.school
            except AttributeError:
                return SchoolStream.objects.none()
        elif hasattr(user, "school"):
            school = user.school

        if not school:
            return SchoolStream.objects.none()

        # Always filter by user's school - important change
        return SchoolStream.objects.filter(school=school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)
