# school/views/event_views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.db import models
from skul_data.scheduler.models.scheduler import SchoolEvent
from skul_data.scheduler.serializers.scheduler import SchoolEventSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser


# 🆕 Create new event (superuser only)
class SchoolEventCreateView(generics.CreateAPIView):
    queryset = SchoolEvent.objects.all()
    serializer_class = SchoolEventSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# 🔍 List events relevant to logged-in user (teacher or parent)
class UserEventListView(generics.ListAPIView):
    serializer_class = SchoolEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = SchoolEvent.objects.none()

        if user.is_superuser:
            # Superuser gets everything
            queryset = SchoolEvent.objects.all()

        elif user.user_type == "teacher":
            queryset = SchoolEvent.objects.filter(
                models.Q(is_for_all_teachers=True) | models.Q(targeted_teachers=user)
            )

        elif user.user_type == "parent":
            queryset = SchoolEvent.objects.filter(
                models.Q(is_for_all_parents=True) | models.Q(targeted_parents=user)
            )

        return queryset.order_by("-start_datetime")


# ✏️ Update event (superuser only)
class SchoolEventUpdateView(generics.RetrieveUpdateAPIView):
    queryset = SchoolEvent.objects.all()
    serializer_class = SchoolEventSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]


# ❌ Delete event (superuser only)
class SchoolEventDeleteView(generics.DestroyAPIView):
    queryset = SchoolEvent.objects.all()
    serializer_class = SchoolEventSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]
