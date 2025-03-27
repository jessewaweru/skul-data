from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.action_logs.views.action_log import ActionLogViewSet

router = DefaultRouter()
router.register(r"action-logs", ActionLogViewSet, basename="actionlog")

urlpatterns = [
    path("", include(router.urls)),
]
