from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
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
from django.db.models import Q
from skul_data.users.models.base_user import User
from skul_data.notifications.serializers.notification import (
    MessageRecipientSerializer,
    MessageListSerializer,
)
import logging

logger = logging.getLogger(__name__)


class MessagePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_read", "message_type"]
    search_fields = ["subject", "body"]
    pagination_class = MessagePagination

    def get_serializer_class(self):
        """Use lightweight serializer for list operations"""
        if self.action == "list" or self.action == "sent":
            return MessageListSerializer
        return MessageSerializer

    def get_queryset(self):
        """Get messages for the current user with proper error handling"""
        if getattr(self, "swagger_fake_view", False):
            return Message.objects.none()

        try:
            user = self.request.user
            logger.info(f"Getting queryset for user {user.id} ({user.user_type})")

            # Get user's school with improved error handling
            user_school = self.get_user_school(user)
            logger.info(f"User school: {user_school}")

            if not user_school:
                logger.warning(f"No school found for user {user.id}")
                # Return empty queryset instead of none to avoid issues
                return Message.objects.filter(id__in=[])

            # Simplify queryset logic based on action
            if self.action == "sent":
                queryset = (
                    Message.objects.filter(sender=user)
                    .select_related("sender", "recipient")
                    .order_by("-created_at")
                )
                logger.info(f"Sent messages count: {queryset.count()}")
                return queryset

            # For inbox - messages received by current user
            # Simplified approach: just get messages where user is recipient
            queryset = (
                Message.objects.filter(recipient=user)
                .select_related("sender", "recipient")
                .order_by("-created_at")
            )

            logger.info(f"Inbox messages count: {queryset.count()}")
            return queryset

        except Exception as e:
            logger.error(
                f"Error in get_queryset for user {getattr(user, 'id', 'unknown')}: {str(e)}"
            )
            logger.exception("Full traceback:")
            return Message.objects.filter(id__in=[])

    def get_user_school(self, user):
        """Get the school associated with the user with better error handling"""
        try:
            logger.info(f"Getting school for user {user.id} (type: {user.user_type})")

            # Check for school_admin_profile
            if hasattr(user, "school_admin_profile"):
                profile = getattr(user, "school_admin_profile", None)
                if profile and hasattr(profile, "school"):
                    school = profile.school
                    logger.info(f"Found school via admin profile: {school}")
                    return school

            # Check for teacher_profile
            if hasattr(user, "teacher_profile"):
                profile = getattr(user, "teacher_profile", None)
                if profile and hasattr(profile, "school"):
                    school = profile.school
                    logger.info(f"Found school via teacher profile: {school}")
                    return school

            # Check for parent_profile
            if hasattr(user, "parent_profile"):
                profile = getattr(user, "parent_profile", None)
                if profile and hasattr(profile, "school"):
                    school = profile.school
                    logger.info(f"Found school via parent profile: {school}")
                    return school

            # Fallback - try to get school from role
            if hasattr(user, "role") and user.role and hasattr(user.role, "school"):
                school = user.role.school
                logger.info(f"Found school via role: {school}")
                return school

            logger.warning(f"No school found for user {user.id}")
            return None

        except Exception as e:
            logger.error(f"Error getting user school for {user.id}: {str(e)}")
            logger.exception("Full traceback:")
            return None

    def list(self, request, *args, **kwargs):
        """List messages with comprehensive error handling"""
        try:
            logger.info(f"List request from user {request.user.id}")

            queryset = self.filter_queryset(self.get_queryset())

            # Apply status filter from query params
            status_filter = request.query_params.get("status")
            if status_filter == "unread":
                queryset = queryset.filter(is_read=False)
            elif status_filter == "read":
                queryset = queryset.filter(is_read=True)

            logger.info(f"Filtered queryset count: {queryset.count()}")

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                logger.info(
                    f"Returning paginated response with {len(serializer.data)} items"
                )
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            logger.info(
                f"Returning non-paginated response with {len(serializer.data)} items"
            )
            return Response(serializer.data)

        except Exception as e:
            logger.error(
                f"Error in list view for user {getattr(request.user, 'id', 'unknown')}: {str(e)}"
            )
            logger.exception("Full traceback:")
            return Response(
                {
                    "error": "Failed to fetch messages",
                    "detail": str(e),
                    "user_id": getattr(request.user, "id", None),
                    "user_type": getattr(request.user, "user_type", None),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single message with error handling"""
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error retrieving message: {str(e)}")
            return Response(
                {"error": "Failed to retrieve message", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """Mark a message as read with error handling"""
        try:
            message = self.get_object()
            # Only allow recipient to mark as read
            if message.recipient != request.user:
                return Response(
                    {"error": "Not authorized to mark this message as read"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            message.is_read = True
            message.save(update_fields=["is_read"])
            logger.info(f"Message {pk} marked as read by user {request.user.id}")
            return Response({"status": "marked as read"})

        except Exception as e:
            logger.error(f"Error marking message {pk} as read: {str(e)}")
            return Response(
                {"error": "Failed to mark message as read", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get unread message count with error handling"""
        try:
            count = Message.objects.filter(
                recipient=request.user, is_read=False
            ).count()
            logger.info(f"Unread count for user {request.user.id}: {count}")
            return Response({"unread_count": count})

        except Exception as e:
            logger.error(
                f"Error getting unread count for user {request.user.id}: {str(e)}"
            )
            return Response({"unread_count": 0})

    @action(detail=False, methods=["get"])
    def sent(self, request):
        """Get sent messages with error handling"""
        try:
            logger.info(f"Sent messages request from user {request.user.id}")

            # The action is detected in get_queryset, so we can use the standard flow
            queryset = self.filter_queryset(self.get_queryset())

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error in sent messages for user {request.user.id}: {str(e)}")
            return Response(
                {"error": "Failed to fetch sent messages", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def recipients(self, request):
        """Get available message recipients with error handling"""
        try:
            user_school = self.get_user_school(request.user)
            if not user_school:
                logger.warning(
                    f"No school found for user {request.user.id} in recipients"
                )
                return Response([])

            # Get all users in the same school except current user
            recipients = (
                User.objects.filter(
                    Q(role__school=user_school)
                    | Q(teacher_profile__school=user_school)
                    | Q(school_admin_profile__school=user_school)
                    | Q(parent_profile__school=user_school)
                )
                .exclude(id=request.user.id)
                .distinct()
            )

            serializer = MessageRecipientSerializer(recipients, many=True)
            logger.info(
                f"Found {len(serializer.data)} recipients for user {request.user.id}"
            )
            return Response(serializer.data)

        except Exception as e:
            logger.error(
                f"Error getting recipients for user {request.user.id}: {str(e)}"
            )
            return Response([])

    @action(detail=False, methods=["post"])
    def bulk_mark_as_read(self, request):
        """Bulk mark messages as read with error handling"""
        try:
            message_ids = request.data.get("message_ids", [])
            if not message_ids:
                return Response(
                    {"error": "No message IDs provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            updated_count = Message.objects.filter(
                id__in=message_ids, recipient=request.user
            ).update(is_read=True)

            logger.info(
                f"Bulk marked {updated_count} messages as read for user {request.user.id}"
            )
            return Response(
                {"status": "messages marked as read", "updated_count": updated_count}
            )

        except Exception as e:
            logger.error(
                f"Error bulk marking as read for user {request.user.id}: {str(e)}"
            )
            return Response(
                {"error": "Failed to mark messages as read", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def perform_create(self, serializer):
        """Create a message with proper error handling and notifications"""
        try:
            message = serializer.save(sender=self.request.user)
            logger.info(
                f"Message created: {message.id} from {message.sender.id} to {message.recipient.id}"
            )

            # Send notifications
            self._send_notifications(message)

        except Exception as e:
            logger.error(f"Error creating message: {str(e)}")
            raise

    def _send_notifications(self, message):
        """Send WebSocket and database notifications for new messages"""
        try:
            # Create database notification
            Notification.objects.create(
                user=message.recipient,
                notification_type="MESSAGE",
                title=f"New message from {message.sender.get_full_name()}",
                message=f"Subject: {message.subject}",
                related_model="Message",
                related_id=message.id,
            )

            # WebSocket notification
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"messages_{message.recipient.id}",
                    {
                        "type": "chat_message",
                        "message_id": message.id,
                        "sender_id": str(message.sender.id),
                        "sender_name": message.sender.get_full_name(),
                        "subject": message.subject,
                        "body": message.body,
                        "is_read": message.is_read,
                        "created_at": message.created_at.isoformat(),
                        "status": "new",
                    },
                )

                # Notify sender that message was delivered
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

            logger.info(f"Notifications sent for message {message.id}")

        except Exception as e:
            logger.error(
                f"Error sending notifications for message {getattr(message, 'id', 'unknown')}: {str(e)}"
            )


class NotificationViewSet(viewsets.ModelViewSet):
    """Enhanced NotificationViewSet with better error handling"""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()

        try:
            return Notification.objects.filter(user=self.request.user).order_by(
                "-created_at"
            )
        except Exception as e:
            logger.error(f"Error in notification queryset: {str(e)}")
            return Notification.objects.filter(id__in=[])

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        try:
            notification = self.get_object()
            notification.is_read = True
            notification.save(update_fields=["is_read"])
            logger.info(f"Notification {pk} marked as read by user {request.user.id}")
            return Response({"status": "marked as read"})
        except Exception as e:
            logger.error(f"Error marking notification {pk} as read: {str(e)}")
            return Response(
                {"error": "Failed to mark notification as read", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        try:
            count = Notification.objects.filter(
                user=request.user, is_read=False
            ).count()
            return Response({"unread_count": count})
        except Exception as e:
            logger.error(f"Error getting unread notification count: {str(e)}")
            return Response({"unread_count": 0})
