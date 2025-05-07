from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.serializers.school_admin import (
    SchoolAdminSerializer,
    SchoolAdminCreateSerializer,
)
from skul_data.users.models.base_user import User
from skul_data.users.permissions.permission import HasRolePermission


class SchoolAdminViewSet(viewsets.ModelViewSet):
    queryset = SchoolAdmin.objects.all().select_related("user", "school")
    # permission_classes = [IsAuthenticated, IsPrimaryAdmin]
    required_permission = "manage_admins"
    permission_classes = [IsAuthenticated, HasRolePermission]

    def get_serializer_class(self):
        if self.action == "create":
            return SchoolAdminCreateSerializer
        return SchoolAdminSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.user_type == User.SCHOOL_ADMIN:
            # Only show admins from the same school
            qs = qs.filter(school=self.request.user.school_admin_profile.school)
        return qs

    def transfer_primary_status(old_primary, new_primary):
        """Transfer primary status from one admin to another atomically."""
        from django.db import transaction

        with transaction.atomic():
            old_primary.is_primary = False
            old_primary.save()

            new_primary.is_primary = True
            new_primary.save()
