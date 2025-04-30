from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.serializers.school_admin import (
    SchoolAdminSerializer,
    SchoolAdminCreateSerializer,
)
from skul_data.users.permissions.permission import IsPrimaryAdmin


class SchoolAdminViewSet(viewsets.ModelViewSet):
    queryset = SchoolAdmin.objects.all().select_related("user", "school")
    permission_classes = [IsAuthenticated, IsPrimaryAdmin]

    def get_serializer_class(self):
        if self.action == "create":
            return SchoolAdminCreateSerializer
        return SchoolAdminSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            # Only show admins from the same school
            qs = qs.filter(school=self.request.user.school_admin_profile.school)
        return qs
