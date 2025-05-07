from rest_framework import viewsets, permissions
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.action_logs.serializers.action_log import ActionLogSerializer
from skul_data.users.permissions.permission import IsAdministrator


class ActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for action logs with filtering capabilities.
    Only accessible by primary school administrators.
    """

    queryset = ActionLog.objects.all().order_by("-timestamp")
    serializer_class = ActionLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = {
        "user_tag": ["exact"],
        "category": ["exact"],
        "content_type__model": ["exact"],
        "timestamp": ["gte", "lte", "exact"],
    }

    search_fields = [
        "action",
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]

    ordering_fields = ["timestamp", "user_tag"]
    ordering = ["-timestamp"]

    @action(detail=False, methods=["get"])
    def model_options(self, request):
        """Get available model options for filtering"""
        content_types = ContentType.objects.filter(
            id__in=ActionLog.objects.values("content_type").distinct()
        )
        options = [{"value": ct.model, "label": ct.name} for ct in content_types]
        return Response(options)

    @action(detail=False, methods=["get"])
    def category_options(self, request):
        """Get available category options"""
        return Response(ActionLog.ActionCategory.choices)
