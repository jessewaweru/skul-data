"""
ASGI config for skul_data project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import skul_data.notifications.routers.routing as notifications  # We'll create this next

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "skul_data.skul_data_main.settings.production"
)

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(notifications.routing.websocket_urlpatterns)
        ),
    }
)
