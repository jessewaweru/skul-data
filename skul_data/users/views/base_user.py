from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Q

from skul_data.users.models.base_user import User
from skul_data.users.serializers.base_user import (
    BaseUserSerializer,
    UserDetailSerializer,
)
from skul_data.users.permissions.permission import (
    HasRolePermission,
    ACCESS_ALL,
    SCHOOL_ADMIN_PERMISSIONS,
)

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing User accounts.
    School admins can manage all users in their school.
    Teachers and parents can only view their own profile.
    """

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = BaseUserSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_users"
    search_fields = ["username", "email", "first_name", "last_name"]
    filterset_fields = ["user_type", "is_active"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return UserDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # School admins can see all users in their school
        if user.user_type == User.SCHOOL_ADMIN and hasattr(user, "school"):
            return queryset.filter(
                Q(school_admin_profile__school=user.school)
                | Q(teacher_profile__school=user.school)
                | Q(parent_profile__school=user.school)
            ).distinct()

        # Teachers can only see their own profile
        elif user.user_type == User.TEACHER:
            return queryset.filter(pk=user.pk)

        # Parents can only see their own profile
        elif user.user_type == User.PARENT:
            return queryset.filter(pk=user.pk)

        # Superusers can see all users
        elif user.is_superuser:
            return queryset

        return queryset.none()

    def get_permissions(self):
        if self.action in ["retrieve", "me"]:
            # Allow any authenticated user to view their own profile
            return [IsAuthenticated()]
        return super().get_permissions()

    def perform_create(self, serializer):
        user = serializer.save()
        # Set password if provided
        if "password" in self.request.data:
            user.set_password(self.request.data["password"])
            user.save()

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get the current user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def set_password(self, request, pk=None):
        """Allow admins to set a user's password"""
        user = self.get_object()
        if "password" not in request.data:
            return Response(
                {"password": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(request.data["password"])
        user.save()
        return Response({"status": "password set"})

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Activate a user account"""
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({"status": "user activated"})

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Deactivate a user account"""
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({"status": "user deactivated"})

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Search users by name, email, or username"""
        query = request.query_params.get("q", "")
        if not query:
            return Response([])

        queryset = (
            self.get_queryset()
            .filter(
                Q(username__icontains=query)
                | Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
            .distinct()[:10]
        )  # Limit to 10 results

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        """Get a user's effective permissions"""
        user = self.get_object()
        permissions = {
            "is_superuser": user.is_superuser,
            "is_staff": user.is_staff,
            "user_type": user.user_type,
            "role_permissions": [],
            "global_permissions": [],
        }

        if user.role:
            permissions["role_permissions"] = list(
                user.role.permissions.values_list("code", flat=True)
            )

        return Response(permissions)
