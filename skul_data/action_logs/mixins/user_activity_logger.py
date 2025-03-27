from django.utils.timezone import now
from django.utils.deprecation import MiddlewareMixin
from models.action_log import Actionlog


class UserActivityLogger(MiddlewareMixin):
    # This automatically logs all user actions when they make requests.
    def log_user_activity(self, request):
        if request.user.is_authenticated:
            Actionlog.objects.create(
                user=request.user,
                user_tag=request.user.user_tag,
                action=f"Accessed {request.path} at {now()}",
            )
