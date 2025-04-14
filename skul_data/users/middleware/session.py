# users/middleware.py
import user_agents
from django.utils import timezone
from skul_data.users.models.session import UserSession


class SessionTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated and hasattr(request, "session"):
            self.process_session(request)

        return response

    def process_session(self, request):
        ua = user_agents.parse(request.META.get("HTTP_USER_AGENT", ""))

        UserSession.objects.update_or_create(
            session_key=request.session.session_key,
            defaults={
                "user": request.user,
                "ip_address": self.get_client_ip(request),
                "device": self.get_device_name(ua),
                "browser": ua.browser.family,
                "os": ua.os.family,
                "last_activity": timezone.now(),
            },
        )

    # Get the ip address of the user
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        return (
            x_forwarded_for.split(",")[0]
            if x_forwarded_for
            else request.META.get("REMOTE_ADDR")
        )

    # Get the device name of the user
    def get_device_name(self, ua):
        if ua.is_mobile:
            return ua.device.family
        elif ua.is_tablet:
            return f"{ua.device.family} Tablet"
        return "Desktop"
