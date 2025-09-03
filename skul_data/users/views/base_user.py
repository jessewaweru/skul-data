from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
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
from django.utils import timezone
from skul_data.users.models.school_admin import AdministratorProfile
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory

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
    pagination_class = None

    def get_serializer_class(self):
        if self.action == "retrieve":
            return UserDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # School admins can see all users in their school + users they can manage
        if user.user_type == User.SCHOOL_ADMIN and hasattr(user, "school"):
            # Get users already connected to this school
            school_connected_users = queryset.filter(
                Q(school_admin_profile__school=user.school)
                | Q(teacher_profile__school=user.school)
                | Q(parent_profile__school=user.school)
                | Q(administrator_profile__school=user.school)
            )

            # For make_administrator functionality, also include OTHER users
            # that don't belong to any school yet (can be managed by any school admin)
            unconnected_users = queryset.filter(
                user_type__in=[User.OTHER],
                school_admin_profile__isnull=True,
                teacher_profile__isnull=True,
                parent_profile__isnull=True,
                administrator_profile__isnull=True,
            )

            return (school_connected_users | unconnected_users).distinct()

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

    # @action(detail=False, methods=["get"])
    # def me(self, request):
    #     """Get the current user's profile"""
    #     serializer = self.get_serializer(request.user)
    #     return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get the current user's profile"""
        serializer = self.get_serializer(request.user)
        # Add debug logging
        print(f"User me endpoint data: {serializer.data}")
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

    @action(
        detail=True,
        methods=["post"],
        url_path="make-administrator",
        url_name="make-administrator",
    )
    def make_administrator(self, request, pk=None):
        user = self.get_object()

        # Prevent making school admin an administrator
        if user.user_type == User.SCHOOL_ADMIN:
            return Response(
                {"error": "School owners cannot be made administrators"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the school from the requesting user (who should be a school admin)
        requesting_user_school = request.user.school
        if not requesting_user_school:
            return Response(
                {"error": "Cannot determine school context"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.user_type == User.TEACHER:
            # For teachers, we'll use the is_administrator flag
            teacher = user.teacher_profile
            teacher.is_administrator = True
            teacher.administrator_since = timezone.now().date()
            teacher.save()

            # Log the action
            log_action(
                user=request.user,
                action=f"Made teacher {user.get_full_name()} an administrator",
                category=ActionCategory.UPDATE,
                obj=teacher,
                metadata={
                    "action_type": "TEACHER_TO_ADMIN",
                    "administrator_since": teacher.administrator_since.isoformat(),
                    "previous_status": False,
                    "new_status": True,
                    "school_id": requesting_user_school.id,
                },
            )

        elif user.user_type not in [User.SCHOOL_ADMIN, User.ADMINISTRATOR]:
            # For other users, create an AdministratorProfile
            admin_profile = AdministratorProfile.objects.create(
                user=user,
                school=requesting_user_school,  # Use requesting user's school
                position=request.data.get("position", "Administrator"),
            )
            # Update user type to ADMINISTRATOR
            user.user_type = User.ADMINISTRATOR
            user.save()

            # Log the action
            log_action(
                user=request.user,
                action=f"Made user {user.get_full_name()} an administrator",
                category=ActionCategory.CREATE,
                obj=admin_profile,
                metadata={
                    "action_type": "USER_TO_ADMIN",
                    "position": admin_profile.position,
                    "access_level": admin_profile.access_level,
                    "school_id": requesting_user_school.id,
                },
            )

        return Response({"status": "user promoted to administrator"})

    @action(
        detail=True,
        methods=["post"],
        url_path="remove-administrator",
        url_name="remove-administrator",
    )
    def remove_administrator(self, request, pk=None):
        user = self.get_object()
        requesting_user_school = request.user.school

        if user.user_type == User.TEACHER and hasattr(user, "teacher_profile"):
            teacher = user.teacher_profile
            previous_status = teacher.is_administrator
            teacher.is_administrator = False
            teacher.administrator_until = timezone.now().date()
            teacher.save()

            # Log the action
            log_action(
                user=request.user,
                action=f"Removed administrator status from teacher {user.get_full_name()}",
                category=ActionCategory.UPDATE,
                obj=teacher,
                metadata={
                    "action_type": "REMOVE_ADMIN_FROM_TEACHER",
                    "previous_status": previous_status,
                    "new_status": False,
                    "administrator_until": teacher.administrator_until.isoformat(),
                    "school_id": requesting_user_school.id,
                },
            )

        elif user.user_type == User.ADMINISTRATOR and hasattr(
            user, "administrator_profile"
        ):
            admin_profile = user.administrator_profile

            # Log before deletion
            log_action(
                user=request.user,
                action=f"Removed administrator status from user {user.get_full_name()}",
                category=ActionCategory.DELETE,
                obj=admin_profile,
                metadata={
                    "action_type": "REMOVE_ADMIN_FROM_USER",
                    "position": admin_profile.position,
                    "access_level": admin_profile.access_level,
                    "school_id": requesting_user_school.id,
                },
            )

            admin_profile.delete()
            user.user_type = User.OTHER
            user.save()

        return Response({"status": "administrator privileges removed"})

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Add search functionality
        search_term = request.query_params.get("search", "")
        if search_term:
            queryset = queryset.filter(
                Q(first_name__icontains=search_term)
                | Q(last_name__icontains=search_term)
                | Q(email__icontains=search_term)
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
