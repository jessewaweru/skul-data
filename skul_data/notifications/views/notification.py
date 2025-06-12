from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from skul_data.notifications.models.notification import Notification, Message
from skul_data.notifications.serializers.notification import (
    NotificationSerializer,
    MessageSerializer,
)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.pagination import PageNumberPagination
from django.db import models
from skul_data.users.models.base_user import User
from skul_data.notifications.serializers.notification import MessageRecipientSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"status": "marked as read"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_read"]
    search_fields = ["subject", "body", "sender__name", "recipient__name"]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        if self.action == "sent":
            return (
                Message.objects.filter(sender=self.request.user)
                .select_related("recipient")
                .order_by("-created_at")
            )

        # Default to inbox
        return (
            Message.objects.filter(recipient=self.request.user)
            .select_related("sender")
            .order_by("-created_at")
        )

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        message = self.get_object()
        message.is_read = True
        message.save()
        return Response({"status": "marked as read"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Message.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=["get"])
    def sent(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def recipients(self, request):
        # Get all teachers and admins in the same school
        school = request.user.school
        recipients = (
            User.objects.filter(
                models.Q(teacher_profile__school=school)
                | models.Q(school_admin_profile__school=school)
            )
            .exclude(id=request.user.id)
            .distinct()
        )

        serializer = MessageRecipientSerializer(recipients, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_mark_as_read(self, request):
        message_ids = request.data.get("message_ids", [])
        Message.objects.filter(id__in=message_ids, recipient=request.user).update(
            is_read=True
        )
        return Response({"status": "messages marked as read"})

    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)

        # Notification logic
        self._send_notifications(message)

    def _send_notifications(self, message):
        # WebSocket notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"messages_{message.recipient.id}",
            {
                "type": "chat_message",
                "message_id": message.id,
                "sender_id": str(
                    message.sender.id
                ),  # Ensure string for JSON serialization
                "sender_name": message.sender.get_full_name(),
                "subject": message.subject,
                "body": message.body,
                "is_read": message.is_read,
                "created_at": message.created_at.isoformat(),
                "status": "new",  # Helps frontend distinguish new messages
            },
        )

        # Also notify sender that message was delivered
        async_to_sync(channel_layer.group_send)(
            f"messages_{message.sender.id}",
            {
                "type": "chat_message",
                "message_id": message.id,
                "status": "delivered",
                "recipient_id": str(message.recipient.id),
                "created_at": message.created_at.isoformat(),
            },
        )
