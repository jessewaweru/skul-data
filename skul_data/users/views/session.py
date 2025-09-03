from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.contrib.sessions.models import Session
from skul_data.users.models.session import UserSession
from skul_data.users.serializers.session import UserSessionSerializer
from skul_data.users.models.base_user import User
from skul_data.users.permissions.permission import HasRolePermission, IsSchoolAdmin
from django.db.models import Q


class UserSessionViewSet(viewsets.ViewSet):
    # permission_classes = [IsAuthenticated, HasRolePermission]
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    # required_permission = "manage_users"

    def get_queryset(self):
        user = self.request.user

        # School admins can see all sessions in their school
        if user.user_type == User.SCHOOL_ADMIN and user.school:
            # Get all users from the same school
            school_user_ids = User.objects.filter(
                Q(school_admin_profile__school=user.school)
                | Q(teacher_profile__school=user.school)
                | Q(parent_profile__school=user.school)
                | Q(administrator_profile__school=user.school)
            ).values_list("id", flat=True)

            return UserSession.objects.filter(
                user_id__in=school_user_ids, session__expire_date__gte=timezone.now()
            ).select_related("user", "session")

        # Teachers with admin privileges can see sessions in their school
        elif (
            user.user_type == User.TEACHER
            and hasattr(user, "teacher_profile")
            and user.teacher_profile.is_administrator
            and user.school
        ):

            school_user_ids = User.objects.filter(
                Q(teacher_profile__school=user.school)
                | Q(parent_profile__school=user.school)
            ).values_list("id", flat=True)

            return UserSession.objects.filter(
                user_id__in=school_user_ids, session__expire_date__gte=timezone.now()
            ).select_related("user", "session")

        # Regular users can only see their own sessions
        return UserSession.objects.filter(
            user=user, session__expire_date__gte=timezone.now()
        ).select_related("user", "session")

    # def list(self, request):
    #     """Get all active sessions based on user permissions"""
    #     queryset = self.get_queryset()
    #     serializer = UserSessionSerializer(queryset, many=True)
    #     return Response(serializer.data)

    def list(self, request):
        print(f"Request user: {request.user}")
        print(f"User school: {request.user.school}")

        school = request.user.school
        if not school:
            print("No school found for user")
            return Response([])

        # Get users in the same school
        school_users = User.objects.filter(
            Q(school_admin_profile__school=school)
            | Q(teacher_profile__school=school)
            | Q(parent_profile__school=school)
            | Q(administrator_profile__school=school)
        )

        print(f"School users found: {school_users.count()}")
        for user in school_users:
            print(f"  - {user.email} ({user.user_type})")

        active_sessions = UserSession.objects.filter(
            user__in=school_users, session__expire_date__gte=timezone.now()
        ).select_related("user", "session")

        print(f"Active sessions found: {active_sessions.count()}")
        for session in active_sessions:
            print(f"  - {session.user.email} on {session.device}")

        serializer = UserSessionSerializer(active_sessions, many=True)
        print(f"Serialized data: {serializer.data}")

        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Get a specific session by session_key"""
        try:
            queryset = self.get_queryset()
            session = queryset.get(session__session_key=pk)
            serializer = UserSessionSerializer(session)
            return Response(serializer.data)
        except UserSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def destroy(self, request, pk=None):
        """Terminate a session by session_key"""
        try:
            queryset = self.get_queryset()
            user_session = queryset.get(session__session_key=pk)
            user_session.session.delete()  # This will cascade delete the UserSession
            return Response(
                {"message": "Session terminated successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )
        except UserSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )
