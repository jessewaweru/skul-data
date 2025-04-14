from rest_framework import viewsets, status
from rest_framework.response import Response
from django.utils import timezone
from django.contrib.sessions.models import Session
from skul_data.users.models.session import UserSession
from skul_data.users.serializers.session import UserSessionSerializer


class SessionViewSet(viewsets.ViewSet):
    def list(self, request):
        # Get all active sessions with user information
        active_sessions = UserSession.objects.filter(
            session__expire_date__gte=timezone.now()
        ).select_related("user", "session")

        serializer = UserSessionSerializer(active_sessions, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        try:
            session = UserSession.objects.get(session__session_key=pk)
            serializer = UserSessionSerializer(session)
            return Response(serializer.data)
        except UserSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def destroy(self, request, pk=None):
        try:
            user_session = UserSession.objects.get(session__session_key=pk)
            user_session.session.delete()  # This will also delete the UserSession via cascade
            return Response(status=status.HTTP_204_NO_CONTENT)
        except UserSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )
