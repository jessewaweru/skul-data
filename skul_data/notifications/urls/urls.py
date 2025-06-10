from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.notifications.views.notification import (
    NotificationViewSet,
    MessageViewSet,
)

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"messages", MessageViewSet, basename="message")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "messages/unread_count/",
        MessageViewSet.as_view({"get": "unread_count"}),
        name="message-unread-count",
    ),
    path(
        "messages/recipients/",
        MessageViewSet.as_view({"get": "recipients"}),
        name="message-recipients",
    ),
    path(
        "messages/bulk_mark_as_read/",
        MessageViewSet.as_view({"post": "bulk_mark_as_read"}),
        name="message-bulk-read",
    ),
]
