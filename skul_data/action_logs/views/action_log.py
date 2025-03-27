from rest_framework import viewsets, permissions
from skul_data.action_logs.models.action_log import Actionlog
from skul_data.action_logs.serializers.action_log import ActionLogSerializer


class ActionLogViewSet(viewsets.ModelViewSet):
    """
    Viewset to manage action logs.
    - Superusers, teachers, and parents can retrieve logs.
    - Actions are recorded automatically.
    """

    queryset = Actionlog.objects.all().order_by("-timestamp")
    serializer_class = ActionLogSerializer
    permission_classes = [permissions.IsAuthenticated]  # Restrict access

    def perform_create(self, serializer):
        """
        Automatically determine which user type performed the action.
        """
        user = self.request.user
        data = {"action": self.request.data.get("action")}

        if hasattr(user, "superuser"):
            data["action_by_superuser"] = user.superuser
        elif hasattr(user, "teacher"):
            data["action_by_teacher"] = user.teacher
        elif hasattr(user, "parent"):
            data["action_by_parent"] = user.parent

        serializer.save(**data)
