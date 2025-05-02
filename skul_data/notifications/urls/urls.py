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
]
