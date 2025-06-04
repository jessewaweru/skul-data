from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from django.db import transaction
import logging
import re
from rest_framework import status
from skul_data.schools.models.schoolclass import ClassTimetable
from django.contrib.auth.models import AnonymousUser
from django.conf import settings

logger = logging.getLogger(__name__)


# class ActionLogMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         response = self.get_response(request)

#         # Skip logging if:
#         # 1. User is not authenticated
#         # 2. Response is a permission denied (403)
#         # 3. Path is admin/static/media
#         if (
#             not request.user.is_authenticated
#             or response.status_code == status.HTTP_403_FORBIDDEN
#             or request.path.startswith(("/admin", "/static", "/media"))
#         ):
#             return response

#         self.log_request(request, response)
#         return response

#     def log_request(self, request, response):
#         try:
#             with transaction.atomic():
#                 # Determine action category - skip for failed requests
#                 if response.status_code >= 400:
#                     return

#                 method_to_category = {
#                     "GET": ActionCategory.VIEW,
#                     "POST": ActionCategory.CREATE,
#                     "PUT": ActionCategory.UPDATE,
#                     "PATCH": ActionCategory.UPDATE,
#                     "DELETE": ActionCategory.DELETE,
#                 }

#                 # Get client IP and user agent
#                 ip = self.get_client_ip(request)
#                 user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

#                 # Prepare metadata
#                 metadata = {
#                     "method": request.method,
#                     "path": request.path,
#                     "status_code": response.status_code,
#                     "user_agent": user_agent,
#                     "ip": ip,
#                 }

#                 # Document specific logging
#                 if "/documents/" in request.path:
#                     metadata.update(
#                         {
#                             "document_operation": True,
#                             "query_params": dict(request.GET),
#                         }
#                     )

#                     if request.method == "GET" and response.status_code == 200:
#                         metadata["document_access"] = True

#                     match = re.search(r"/documents/(\d+)/", request.path)
#                     if match:
#                         metadata["document_id"] = int(match.group(1))

#                     if "/share/download/" in request.path:
#                         token_match = re.search(
#                             r"/share/download/([^/]+)/", request.path
#                         )
#                         if token_match:
#                             metadata["token"] = token_match.group(1)

#                 # Add school ID if available
#                 if hasattr(request.user, "administered_school"):
#                     metadata["school_id"] = request.user.administered_school.id

#                 ActionLog.objects.create(
#                     user=request.user,
#                     action=f"{request.method} {request.path}",
#                     category=method_to_category.get(
#                         request.method, ActionCategory.OTHER
#                     ),
#                     ip_address=ip,
#                     user_agent=user_agent,
#                     metadata=metadata,
#                 )
#         except Exception as e:
#             logger.error(f"ActionLog creation failed: {str(e)}")

#     def get_client_ip(self, request):
#         x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
#         return (
#             x_forwarded_for.split(",")[0]
#             if x_forwarded_for
#             else request.META.get("REMOTE_ADDR")
#         )


class ActionLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Skip logging if:
        # 1. User is not authenticated
        # 2. Response is a permission denied (403)
        # 3. Path is admin/static/media
        # 4. In test mode
        if (
            isinstance(request.user, AnonymousUser)
            or response.status_code == status.HTTP_403_FORBIDDEN
            or any(
                request.path.startswith(p) for p in ("/admin/", "/static/", "/media/")
            )
            or getattr(settings, "TEST_MODE", False)
        ):
            return response

        self.log_request(request, response)
        return response

    def log_request(self, request, response):
        try:
            with transaction.atomic():
                # Determine action category - skip for failed requests
                if response.status_code >= 400:
                    return

                method_to_category = {
                    "GET": ActionCategory.VIEW,
                    "POST": ActionCategory.CREATE,
                    "PUT": ActionCategory.UPDATE,
                    "PATCH": ActionCategory.UPDATE,
                    "DELETE": ActionCategory.DELETE,
                }

                # Get client IP and user agent
                ip = self.get_client_ip(request)
                user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

                # Prepare metadata
                metadata = {
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "user_agent": user_agent,
                    "ip": ip,
                }

                # Document specific logging
                if "/documents/" in request.path:
                    metadata.update(
                        {
                            "document_operation": True,
                            "query_params": dict(request.GET),
                        }
                    )

                    if request.method == "GET" and response.status_code == 200:
                        metadata["document_access"] = True

                    match = re.search(r"/documents/(\d+)/", request.path)
                    if match:
                        metadata["document_id"] = int(match.group(1))

                    if "/share/download/" in request.path:
                        token_match = re.search(
                            r"/share/download/([^/]+)/", request.path
                        )
                        if token_match:
                            metadata["token"] = token_match.group(1)

                # Timetable specific logging
                if "/timetables/" in request.path:
                    metadata.update(
                        {
                            "timetable_operation": True,
                            "query_params": dict(request.GET),
                        }
                    )

                    # Better file type detection
                    if request.FILES:
                        uploaded_file = list(request.FILES.values())[
                            0
                        ]  # Get first file
                        file_type = uploaded_file.content_type.split("/")[
                            -1
                        ]  # Get subtype
                        if "." in uploaded_file.name:
                            file_type = uploaded_file.name.split(".")[-1].lower()
                        metadata["file_type"] = file_type

                    # Capture timetable ID if present in URL
                    timetable_match = re.search(r"/timetables/(\d+)/", request.path)
                    if timetable_match:
                        metadata["timetable_id"] = int(timetable_match.group(1))

                    # Special handling for file downloads
                    if request.method == "GET" and response.status_code == 200:
                        metadata["file_download"] = True
                        content_disposition = response.headers.get(
                            "Content-Disposition", ""
                        )
                        if "filename=" in content_disposition:
                            metadata["downloaded_filename"] = content_disposition.split(
                                "filename="
                            )[1].strip('"')

                # Add school ID if available
                if hasattr(request.user, "administered_school"):
                    metadata["school_id"] = request.user.administered_school.id

                # Add class ID if available in timetable operations
                if "/timetables/" in request.path and "timetable_id" in metadata:
                    try:
                        timetable = ClassTimetable.objects.get(
                            pk=metadata["timetable_id"]
                        )
                        metadata["class_id"] = timetable.school_class.id
                        metadata["class_name"] = timetable.school_class.name
                    except ClassTimetable.DoesNotExist:
                        pass

                ActionLog.objects.create(
                    user=request.user,
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
