from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from django.db import transaction
import logging
import re

logger = logging.getLogger(__name__)


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
        if request.path.startswith(("/admin", "/static", "/media")):
            return

        try:
            with transaction.atomic():
                # Determine action category
                method_to_category = {
                    "GET": ActionCategory.VIEW,
                    "POST": ActionCategory.CREATE,
                    "PUT": ActionCategory.UPDATE,
                    "PATCH": ActionCategory.UPDATE,
                    "DELETE": ActionCategory.DELETE,
                }

                # Get client IP and user agent
                ip = self.get_client_ip(request)
                user_agent = request.META.get("HTTP_USER_AGENT", "")[
                    :500
                ]  # Truncate if needed

                # Prepare metadata
                metadata = {
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "user_agent": user_agent,
                    "ip": ip,
                }

                # ===== ENHANCED DOCUMENT LOGGING =====
                if "/documents/" in request.path:
                    metadata.update(
                        {
                            "document_operation": True,
                            "query_params": dict(request.GET),
                        }
                    )

                    # Track document view/access patterns
                    if request.method == "GET" and response.status_code == 200:
                        metadata["document_access"] = True

                    # Capture document ID from URL if available
                    match = re.search(r"/documents/(\d+)/", request.path)
                    if match:
                        metadata["document_id"] = int(match.group(1))

                    # Handle share link downloads
                    if "/share/download/" in request.path:
                        # Extract token from URL
                        token_match = re.search(
                            r"/share/download/([^/]+)/", request.path
                        )
                        if token_match:
                            metadata["token"] = token_match.group(1)
                # ===== END ENHANCEMENT =====

                # Add school ID if available
                if hasattr(request.user, "administered_school"):
                    metadata["school_id"] = request.user.administered_school.id

                ActionLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action=f"{request.method} {request.path}",
                    category=method_to_category.get(
                        request.method, ActionCategory.OTHER
                    ),
                    ip_address=ip,
                    user_agent=user_agent,
                    metadata=metadata,
                )
        except Exception as e:
            logger.error(f"ActionLog creation failed: {str(e)}")

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        return (
            x_forwarded_for.split(",")[0]
            if x_forwarded_for
            else request.META.get("REMOTE_ADDR")
        )
