from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.serializers.school_admin import (
    SchoolAdminSerializer,
    SchoolAdminCreateSerializer,
)
from skul_data.users.models.base_user import User
from skul_data.users.permissions.permission import HasRolePermission
from skul_data.users.models.school_admin import AdministratorProfile
from skul_data.users.serializers.school_admin import (
    AdministratorProfileSerializer,
    AdministratorProfileCreateSerializer,
    AdministratorProfileUpdateSerializer,
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.response import Response
from skul_data.users.permissions.permission import IsAdministrator, IsSchoolAdmin


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


class AdministratorProfileViewSet(viewsets.ModelViewSet):
    queryset = AdministratorProfile.objects.filter(is_active=True)
    serializer_class = AdministratorProfileSerializer
    # permission_classes = [IsSchoolAdmin | IsAdministrator]
    permission_classes = [IsAuthenticated, (IsSchoolAdmin | IsAdministrator)]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "school",
        "access_level",
        "is_active",
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "position",
    ]
    ordering_fields = ["date_appointed", "user__last_name"]
    ordering = ["-date_appointed"]

    def get_serializer_class(self):
        if self.action == "create":
            return AdministratorProfileCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return AdministratorProfileUpdateSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # School owners see all administrators in their school
        if IsSchoolAdmin().has_permission(self.request, self):
            return queryset.filter(school=user.school)

        # Administrators only see themselves
        elif IsAdministrator().has_permission(self.request, self):
            return queryset.filter(user=user)

        return queryset.none()

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        administrator = self.get_object()
        administrator.is_active = False
        administrator.save()

        # Optionally change user type if needed
        user = administrator.user
        user.user_type = User.OTHER  # Or whatever default you want
        user.save()

        return Response({"status": "administrator deactivated"})

    @action(
        detail=False,
        methods=["get"],
        url_path="permissions-options",
        url_name="permissions_options",
    )
    def permissions_options(self, request):
        """Return available permissions options for the frontend"""
        permissions = [
            {
                "code": "manage_users",
                "name": "Manage Users",
                "description": "Create, edit and delete user accounts",
            },
            {
                "code": "manage_teachers",
                "name": "Manage Teachers",
                "description": "Add and manage teacher profiles",
            },
            {
                "code": "manage_students",
                "name": "Manage Students",
                "description": "Add and manage student records",
            },
            {
                "code": "manage_parents",
                "name": "Manage Parents",
                "description": "Add and manage parent accounts",
            },
            {
                "code": "manage_classes",
                "name": "Manage Classes",
                "description": "Create and organize class structures",
            },
            {
                "code": "manage_documents",
                "name": "Manage Documents",
                "description": "Upload and organize school documents",
            },
            {
                "code": "manage_reports",
                "name": "Manage Reports",
                "description": "Generate and view school reports",
            },
            {
                "code": "view_analytics",
                "name": "View Analytics",
                "description": "Access school performance analytics",
            },
            {
                "code": "manage_calendar",
                "name": "Manage Calendar",
                "description": "Create and edit school events",
            },
            {
                "code": "system_settings",
                "name": "System Settings",
                "description": "Configure system-wide settings",
            },
        ]
        return Response(permissions)
