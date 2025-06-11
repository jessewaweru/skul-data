from django.urls import re_path
from skul_data.notifications.consumers import consumer

websocket_urlpatterns = [
    re_path(
        r"^ws/notifications/(?P<user_id>\w+)/$", consumer.NotificationConsumer.as_asgi()
    ),
    re_path(r"^ws/messages/(?P<user_id>\w+)/$", consumer.MessageConsumer.as_asgi()),
]
