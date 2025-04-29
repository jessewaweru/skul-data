from skul_data.action_logs.models.action_log import ActionLog, ActionCategory


class ActionLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            self.log_request(request, response)

        return response

    def log_request(self, request, response):
        # Skip logging for certain paths
        if request.path.startswith("/admin/") or request.path.startswith("/static/"):
            return

        # Determine action category based on request method
        method_to_category = {
            "GET": ActionCategory.VIEW,
            "POST": ActionCategory.CREATE,
            "PUT": ActionCategory.UPDATE,
            "PATCH": ActionCategory.UPDATE,
            "DELETE": ActionCategory.DELETE,
        }

        category = method_to_category.get(request.method, ActionCategory.OTHER)

        # Create the log entry
        ActionLog.objects.create(
            user=request.user,
            action=f"{request.method} {request.path}",
            category=category,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            metadata={
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "query_params": dict(request.GET),
                "data": (
                    request.POST.dict()
                    if request.method in ["POST", "PUT", "PATCH"]
                    else None
                ),
            },
        )

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        return (
            x_forwarded_for.split(",")[0]
            if x_forwarded_for
            else request.META.get("REMOTE_ADDR")
        )
