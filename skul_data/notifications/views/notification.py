from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from skul_data.notifications.models.notification import Notification, Message
from skul_data.notifications.serializers.notification import (
    NotificationSerializer,
    MessageSerializer,
)


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

    def get_queryset(self):
        return Message.objects.filter(recipient=self.request.user).order_by(
            "-created_at"
        )

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        message = self.get_object()
        message.is_read = True
        message.save()
        return Response({"status": "marked as read"})

    @action(detail=False, methods=["get"])
    def sent(self, request):
        sent_messages = Message.objects.filter(sender=request.user).order_by(
            "-created_at"
        )
        serializer = self.get_serializer(sent_messages, many=True)
        return Response(serializer.data)
