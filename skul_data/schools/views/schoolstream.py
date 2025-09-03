from rest_framework import viewsets
from skul_data.schools.models.schoolstream import SchoolStream
from skul_data.schools.serializers.schoolstream import (
    SchoolStreamSerializer,
    SchoolStreamCreateSerializer,
)
from skul_data.users.permissions.permission import IsAdministrator
from skul_data.users.models.base_user import User
from skul_data.users.permissions.permission import HasRolePermission
from rest_framework.permissions import IsAuthenticated
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.action_logs.utils.action_log import log_action


class SchoolStreamViewSet(viewsets.ModelViewSet):
    """Endpoint that allows school streams to be viewed or edited."""

    serializer_class = SchoolStreamSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]

    # Set required permissions for HasRolePermission
    required_permission_get = "view_classes"  # or create a specific stream permission
    required_permission_post = "manage_classes"
    required_permission_put = "manage_classes"
    required_permission_delete = "manage_classes"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SchoolStreamCreateSerializer
        return SchoolStreamSerializer

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return SchoolStream.objects.none()

        # Debug: Print user info
        print(f"User: {user}, User type: {user.user_type}")

        # Get the user's school - Try multiple methods
        school = None

        # Method 1: Through role (most likely based on your API response)
        if hasattr(user, "role") and hasattr(user.role, "school"):
            school = user.role.school
            print(f"School from role: {school}")

        # Method 2: Direct school admin profile
        elif user.user_type == User.SCHOOL_ADMIN:
            try:
                if hasattr(user, "school_admin_profile"):
                    school = user.school_admin_profile.school
                elif hasattr(user, "schooladmin"):
                    school = user.schooladmin.school
                print(f"School Admin - School found: {school}")
            except AttributeError as e:
                print(f"Error getting school for admin: {e}")

        # Method 3: Direct school access
        elif hasattr(user, "school"):
            school = user.school
            print(f"Direct school access - School: {school}")

        if not school:
            print("No school assigned to user")
            # Try one more method - check if school ID is available
            if hasattr(user, "role") and hasattr(user.role, "school_id"):
                from skul_data.schools.models.school import School

                try:
                    school = School.objects.get(id=user.role.school_id)
                    print(f"School from role.school_id: {school}")
                except School.DoesNotExist:
                    pass

            if not school:
                return SchoolStream.objects.none()

        # Filter by user's school
        queryset = SchoolStream.objects.filter(school=school)
        print(f"Filtered queryset count: {queryset.count()}")

        return queryset

    def perform_create(self, serializer):
        user = self.request.user

        # Get user's school using the same logic as get_queryset
        school = None

        # Method 1: Through role (most likely)
        if hasattr(user, "role") and hasattr(user.role, "school"):
            school = user.role.school
        elif user.user_type == User.SCHOOL_ADMIN:
            try:
                if hasattr(user, "school_admin_profile"):
                    school = user.school_admin_profile.school
                elif hasattr(user, "schooladmin"):
                    school = user.schooladmin.school
            except AttributeError:
                pass
        elif hasattr(user, "school"):
            school = user.school

        if not school:
            # Try getting school by ID from role
            if hasattr(user, "role") and hasattr(user.role, "school_id"):
                from skul_data.schools.models.school import School

                try:
                    school = School.objects.get(id=user.role.school_id)
                except School.DoesNotExist:
                    pass

        if not school:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("No school associated with user")

        stream = serializer.save(school=school)

        # Log the action
        log_action(
            user=user,
            action=f"Created stream '{stream.name}'",
            category=ActionCategory.CREATE,
            obj=stream,
            metadata={"stream_name": stream.name, "school": str(school)},
        )

    def perform_update(self, serializer):
        stream = serializer.save()

        # Log the action
        log_action(
            user=self.request.user,
            action=f"Updated stream '{stream.name}'",
            category=ActionCategory.UPDATE,
            obj=stream,
            metadata={
                "stream_name": stream.name,
            },
        )

    def perform_destroy(self, instance):
        # Log the action before deletion
        log_action(
            user=self.request.user,
            action=f"Deleted stream '{instance.name}'",
            category=ActionCategory.DELETE,
            obj=instance,
            metadata={"stream_name": instance.name, "stream_id": instance.id},
        )
        instance.delete()

    def list(self, request, *args, **kwargs):
        """Override list to add debug info"""
        queryset = self.filter_queryset(self.get_queryset())

        print(f"Final queryset for list: {queryset.count()} streams")
        for stream in queryset:
            print(f"  - {stream.name} (ID: {stream.id})")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
