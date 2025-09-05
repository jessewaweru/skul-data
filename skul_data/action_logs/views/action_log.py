from rest_framework import viewsets, permissions
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.action_logs.serializers.action_log import ActionLogSerializer
from skul_data.users.permissions.permission import IsAdministrator, IsSchoolAdmin
from skul_data.action_logs.models.action_log import ActionCategory


class ActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for action logs with filtering capabilities.
    Only accessible by primary school administrators.
    """

    queryset = ActionLog.objects.all().order_by("-timestamp")
    serializer_class = ActionLogSerializer
    # permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin]
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
        return Response(ActionCategory.choices)


# class ActionLogViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     Viewset for action logs with filtering capabilities.
#     Only accessible by school administrators.
#     """

#     queryset = (
#         ActionLog.objects.all()
#         .select_related("user", "content_type")
#         .order_by("-timestamp")
#     )
#     serializer_class = ActionLogSerializer
#     permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin]
#     filter_backends = [
#         DjangoFilterBackend,
#         filters.SearchFilter,
#         filters.OrderingFilter,
#     ]

#     filterset_fields = {
#         "user_tag": ["exact"],
#         "category": ["exact"],
#         "content_type__model": ["exact"],
#         "timestamp": ["gte", "lte", "exact", "date"],
#     }

#     search_fields = [
#         "action",
#         "user__username",
#         "user__email",
#         "user__first_name",
#         "user__last_name",
#         "user_tag",
#     ]

#     ordering_fields = ["timestamp", "user_tag", "category"]
#     ordering = ["-timestamp"]

#     def get_queryset(self):
#         """
#         Filter logs to show only logs from the user's school
#         """
#         queryset = super().get_queryset()
#         user = self.request.user

#         # Get the user's school
#         if hasattr(user, "school_admin_profile") and user.school_admin_profile:
#             school = user.school_admin_profile.school
#             # Filter logs by users from the same school
#             queryset = queryset.filter(
#                 user__isnull=False, user__school_admin_profile__school=school
#             ).union(
#                 # Include system logs (user=None) for the school
#                 queryset.filter(user__isnull=True)
#             )

#         return queryset

#     def list(self, request, *args, **kwargs):
#         """
#         Override list to handle CSV export
#         """
#         # Check for CSV export
#         if request.query_params.get("export") == "csv":
#             return self.export_csv(request)

#         return super().list(request, *args, **kwargs)

#     def export_csv(self, request):
#         """
#         Export filtered action logs as CSV
#         """
#         # Apply filters to get the queryset
#         queryset = self.filter_queryset(self.get_queryset())

#         # Create CSV response
#         response = HttpResponse(content_type="text/csv")
#         response["Content-Disposition"] = (
#             f'attachment; filename="action_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
#         )

#         writer = csv.writer(response)

#         # Write header
#         writer.writerow(
#             [
#                 "Timestamp",
#                 "User Tag",
#                 "User Name",
#                 "Action",
#                 "Category",
#                 "Affected Model",
#                 "Affected Object",
#                 "IP Address",
#                 "User Agent",
#             ]
#         )

#         # Write data rows
#         for log in queryset[:1000]:  # Limit to 1000 records for performance
#             user_name = ""
#             if log.user:
#                 user_name = f"{log.user.first_name} {log.user.last_name}".strip()
#                 if not user_name:
#                     user_name = log.user.username

#             writer.writerow(
#                 [
#                     log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
#                     str(log.user_tag),
#                     user_name,
#                     log.action,
#                     log.get_category_display(),
#                     log.affected_model or "",
#                     log.affected_object or "",
#                     log.ip_address or "",
#                     log.user_agent or "",
#                 ]
#             )

#         return response

#     @action(detail=False, methods=["get"])
#     def model_options(self, request):
#         """Get available model options for filtering"""
#         try:
#             # Get content types that actually have action logs
#             content_types = ContentType.objects.filter(
#                 id__in=ActionLog.objects.exclude(content_type__isnull=True)
#                 .values_list("content_type", flat=True)
#                 .distinct()
#             ).order_by("model")

#             options = [
#                 {"value": ct.model, "label": ct.name.title()} for ct in content_types
#             ]

#             return Response(options)
#         except Exception as e:
#             return Response({"error": str(e)}, status=500)

#     @action(detail=False, methods=["get"])
#     def category_options(self, request):
#         """Get available category options"""
#         try:
#             return Response(ActionCategory.choices)
#         except Exception as e:
#             return Response({"error": str(e)}, status=500)

#     @action(detail=False, methods=["get"])
#     def stats(self, request):
#         """Get action log statistics"""
#         try:
#             queryset = self.filter_queryset(self.get_queryset())

#             # Basic stats
#             total_logs = queryset.count()

#             # Category breakdown
#             category_stats = {}
#             for category in ActionCategory.choices:
#                 count = queryset.filter(category=category[0]).count()
#                 if count > 0:
#                     category_stats[category[1]] = count

#             # User activity (top 10)
#             user_activity = (
#                 queryset.exclude(user__isnull=True)
#                 .values("user_tag", "user__first_name", "user__last_name")
#                 .annotate(count=models.Count("id"))
#                 .order_by("-count")[:10]
#             )

#             # Time range
#             oldest = queryset.order_by("timestamp").first()
#             newest = queryset.order_by("-timestamp").first()

#             stats = {
#                 "total_logs": total_logs,
#                 "category_breakdown": category_stats,
#                 "top_users": [
#                     {
#                         "user_tag": str(user["user_tag"]),
#                         "name": f"{user['user__first_name']} {user['user__last_name']}".strip(),
#                         "count": user["count"],
#                     }
#                     for user in user_activity
#                 ],
#                 "time_range": {
#                     "oldest": oldest.timestamp.isoformat() if oldest else None,
#                     "newest": newest.timestamp.isoformat() if newest else None,
#                 },
#             }

#             return Response(stats)
#         except Exception as e:
#             return Response({"error": str(e)}, status=500)
