from rest_framework import viewsets, permissions
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import Permission
from skul_data.users.models.role import Role
from skul_data.users.serializers.role import PermissionSerializer, RoleSerializer
from skul_data.users.permissions.permission import HasRolePermission


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated]


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    # permission_classes = [permissions.IsAuthenticated]
    required_permission = "manage_roles"
    permission_classes = [IsAuthenticated, HasRolePermission]

    def get_queryset(self):
        # Only show roles for the current user's school
        return Role.objects.filter(school=self.request.user.school)

    def perform_create(self, serializer):
        # Automatically assign the school from current user
        serializer.save(school=self.request.user.school)

    def get_permissions(self):
        if self.action in ["create", "update", "destroy"]:
            self.permission_classes = [permissions.IsAdminUser]
        return super().get_permissions()
