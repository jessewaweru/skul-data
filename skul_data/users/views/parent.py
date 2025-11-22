from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from skul_data.users.permissions.permission import IsAdministrator
from skul_data.users.models.parent import Parent, ParentStatusChange, ParentNotification
from skul_data.students.models.student import Student
from skul_data.users.serializers.parent import (
    ParentSerializer,
    ParentNotificationSerializer,
    ParentStatusChangeSerializer,
    ParentCreateSerializer,
    ParentChildAssignmentSerializer,
    ParentNotificationPreferenceSerializer,
    ParentStatusUpdateSerializer,
)
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.users.permissions.permission import HasRolePermission
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.reports.serializers.academic_record import AcademicRecordSerializer
from skul_data.users.models.base_user import User
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.users.utils.parent import send_parent_email
from openpyxl import Workbook
from skul_data.users.serializers.parent import ParentBulkImportSerializer
from rest_framework import status
from django.db import transaction
from django.http import HttpResponse
import os
import pandas as pd
import logging
import re

logger = logging.getLogger(__name__)


class ParentViewSet(viewsets.ModelViewSet):
    queryset = Parent.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "status",
        "school",
        "receive_email_notifications",
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "phone_number",
        "children__first_name",
        "children__last_name",
    ]

    permission_classes = [IsAuthenticated, HasRolePermission]

    # Define permissions for each action
    required_permission = "view_parents"
    required_permission_post = "create_parent"
    required_permission_put = "update_parent"
    required_permission_patch = "update_parent"
    required_permission_delete = "manage_parents"

    def get_serializer_class(self):
        if self.action == "create":
            return ParentCreateSerializer
        elif self.action in ["change_status", "activate", "deactivate"]:
            return ParentStatusUpdateSerializer  # Use the new name
        elif self.action == "assign_children":
            return ParentChildAssignmentSerializer
        elif self.action == "update_notification_preferences":
            return ParentNotificationPreferenceSerializer
        return ParentSerializer

    # def get_permissions(self):
    #     if self.action in ["create", "update", "partial_update", "destroy"]:
    #         return [IsAdministrator()]
    #     elif self.action in ["change_status", "assign_children"]:
    #         return [IsAdministrator()]
    #     return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Get school from user
        school = user.school  # Using your User model's school property

        if not school:
            return Parent.objects.none()

        # Always filter by school
        queryset = queryset.filter(school=school)

        # Parents can only see their own profile
        if user.user_type == User.PARENT:
            return queryset.filter(user=user)

        return queryset

    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        parent = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_status = parent.status
        new_status = serializer.validated_data["status"]

        # Log before changing status - use "Changed" to match signal
        log_action(
            user=request.user,
            action=f"Changed parent status from {old_status} to {new_status}",
            category=ActionCategory.UPDATE,
            obj=parent,
            metadata={
                "reason": serializer.validated_data.get("reason", ""),
                "old_status": old_status,
                "new_status": new_status,
            },
        )

        parent.status = new_status
        parent.save()

        ParentStatusChange.objects.create(
            parent=parent,
            changed_by=request.user,
            from_status=old_status,
            to_status=new_status,
            reason=serializer.validated_data.get("reason", ""),
        )

        return Response(ParentSerializer(parent).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        parent = self.get_object()
        parent.status = "ACTIVE"
        parent.save()
        return Response(ParentSerializer(parent).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        parent = self.get_object()
        parent.status = "INACTIVE"
        parent.save()
        return Response(ParentSerializer(parent).data)

    @action(detail=True, methods=["post"])
    def assign_children(self, request, pk=None):
        parent = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        students = serializer.validated_data["student_ids"]
        action = serializer.validated_data["action"]
        current_children = list(parent.children.values_list("id", flat=True))

        # Log before making changes
        log_action(
            user=request.user,
            action=f"Modifying parent-child relationships: {action}",
            category=ActionCategory.UPDATE,
            obj=parent,
            metadata={
                "current_children": current_children,
                "new_children": [s.id for s in students],
                "operation": action,
            },
        )

        if action == "ADD":
            parent.children.add(*students)
        elif action == "REMOVE":
            parent.children.remove(*students)
        elif action == "REPLACE":
            parent.children.set(students)

        return Response(ParentSerializer(parent).data)

    @action(detail=True, methods=["get"])
    def children_academic_records(self, request, pk=None):
        parent = self.get_object()
        records = AcademicRecord.objects.filter(
            student__in=parent.children.all(), is_published=True
        )
        serializer = AcademicRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def children_attendance(self, request, pk=None):
        parent = self.get_object()
        attendance = StudentAttendance.objects.filter(student__in=parent.children.all())
        serializer = StudentAttendanceSerializer(attendance, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def shared_documents(self, request, pk=None):
        parent = self.get_object()
        documents = Document.objects.filter(
            Q(related_students__in=parent.children.all()) | Q(is_public=True)
        ).distinct()
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def notifications(self, request, pk=None):
        parent = self.get_object()
        notifications = ParentNotification.objects.filter(parent=parent).order_by(
            "-created_at"
        )
        serializer = ParentNotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        parent = self.get_object()
        message = request.data.get("message")
        if not message:
            return Response(
                {"detail": "Message is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Send email
        send_parent_email(parent, subject="Message from School", message=message)

        # Create in-app notification
        notification = ParentNotification.objects.create(
            parent=parent,
            message=message,
            notification_type="MANUAL",  # You could also use a constant if you have enums
            sent_by=request.user,
        )

        return Response({"status": "message sent", "notification_id": notification.id})

    @action(detail=True, methods=["put", "patch"])
    def update_notification_preferences(self, request, pk=None):
        parent = self.get_object()
        serializer = self.get_serializer(parent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        # Basic counts
        total_parents = queryset.count()
        parents_by_status = queryset.values("status").annotate(count=Count("id"))

        # Children distribution
        children_distribution = (
            queryset.annotate(child_count=Count("children"))
            .values("child_count")
            .annotate(parent_count=Count("id"))
            .order_by("child_count")
        )

        # Activity metrics
        active_parents = queryset.filter(
            user__last_login__gte=timezone.now() - timedelta(days=30)
        ).count()

        return Response(
            {
                "total_parents": total_parents,
                "parents_by_status": parents_by_status,
                "children_distribution": children_distribution,
                "active_parents": active_parents,
            }
        )

    @action(detail=False, methods=["post"], url_path="bulk-import")
    def bulk_import(self, request):
        serializer = ParentBulkImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file = serializer.validated_data["file"]
        send_welcome_email = serializer.validated_data["send_welcome_email"]
        default_status = serializer.validated_data["default_status"]

        try:
            # Read the file based on its type
            ext = os.path.splitext(file.name)[1].lower()

            # if ext == ".csv":
            #     df = pd.read_csv(file)
            # else:  # Excel files
            #     df = pd.read_excel(file, sheet_name=0)

            # # In bulk_import method
            # if ext == ".csv":
            #     df = pd.read_csv(file, dtype=str)  # Force all columns as strings
            # else:
            #     df = pd.read_excel(
            #         file, sheet_name=0, dtype=str
            #     )  # Force all columns as strings

            if ext == ".csv":
                # Read CSV with phone_number as string to prevent float conversion
                df = pd.read_csv(file, dtype={"phone_number": "str"})
            else:  # Excel files
                # Read Excel with phone_number as string
                df = pd.read_excel(file, sheet_name=0, dtype={"phone_number": "str"})

            # Validate required columns
            required_columns = {"email", "first_name", "last_name"}
            if not required_columns.issubset(df.columns):
                missing = required_columns - set(df.columns)
                return Response(
                    {"error": f'Missing required columns: {", ".join(missing)}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get school from the request user
            if hasattr(request.user, "school_admin_profile"):
                school = request.user.school_admin_profile.school
            else:
                school = request.user.school

            if not school:
                return Response(
                    {"error": "No school associated with user"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Process each row
            results = {"success": [], "errors": []}

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Skip empty rows
                        if (
                            pd.isna(row.get("email"))
                            or not str(row.get("email")).strip()
                        ):
                            continue

                        # Validate required fields
                        required_fields = ["email", "first_name", "last_name"]
                        missing_fields = []
                        for field in required_fields:
                            if (
                                pd.isna(row.get(field))
                                or not str(row.get(field)).strip()
                            ):
                                missing_fields.append(field)

                        if missing_fields:
                            results["errors"].append(
                                {
                                    "row": index + 2,
                                    "email": str(row.get("email", "")).strip(),
                                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                                }
                            )
                            continue

                        # Prepare parent data - ENSURE STATUS IS SET
                        parent_data = {
                            "email": str(row["email"]).strip(),
                            "first_name": str(row["first_name"]).strip(),
                            "last_name": str(row["last_name"]).strip(),
                            "school": school.id,
                            "status": default_status,  # This should be preserved
                        }

                        # Handle optional fields with proper null checking
                        # if "phone_number" in row and pd.notna(row["phone_number"]):
                        #     parent_data["phone_number"] = str(
                        #         row["phone_number"]
                        #     ).strip()

                        if (
                            "phone_number" in row
                            and pd.notna(row["phone_number"])
                            and str(row["phone_number"]).strip() != "nan"
                        ):
                            phone_str = str(row["phone_number"]).strip()
                            # Add + prefix if missing
                            if not phone_str.startswith("+"):
                                phone_str = "+" + phone_str
                            parent_data["phone_number"] = phone_str

                        if "address" in row and pd.notna(row["address"]):
                            parent_data["address"] = str(row["address"]).strip()

                        if "occupation" in row and pd.notna(row["occupation"]):
                            parent_data["occupation"] = str(row["occupation"]).strip()

                        if "preferred_language" in row and pd.notna(
                            row["preferred_language"]
                        ):
                            parent_data["preferred_language"] = str(
                                row["preferred_language"]
                            ).strip()

                        # Handle children assignment (your existing logic)
                        children_ids = []
                        if "children_ids" in row and pd.notna(row["children_ids"]):
                            try:
                                children_str = str(row["children_ids"]).strip()
                                if children_str:
                                    # Handle multiple separators: comma, semicolon, or space
                                    id_parts = re.split(r"[,;\s]", children_str)
                                    for id_part in id_parts:
                                        id_clean = id_part.strip()
                                        if id_clean and id_clean.isdigit():
                                            children_ids.append(int(id_clean))
                            except (ValueError, AttributeError) as e:
                                results["errors"].append(
                                    {
                                        "row": index + 2,
                                        "email": parent_data.get("email", ""),
                                        "error": f"Invalid children_ids format: {str(e)}",
                                    }
                                )
                                continue

                        # Validate children exist in the school
                        if children_ids:
                            valid_children = Student.objects.filter(
                                id__in=children_ids, school=school
                            )
                            invalid_ids = set(children_ids) - set(
                                valid_children.values_list("id", flat=True)
                            )
                            if invalid_ids:
                                results["errors"].append(
                                    {
                                        "row": index + 2,
                                        "email": parent_data.get("email", ""),
                                        "error": f"Invalid student IDs: {list(invalid_ids)}",
                                    }
                                )
                                continue

                        # Create parent
                        parent_serializer = ParentCreateSerializer(
                            data=parent_data, context={"request": request}
                        )

                        if parent_serializer.is_valid():
                            parent = parent_serializer.save()

                            # Assign children if specified and valid
                            if children_ids:
                                children = Student.objects.filter(
                                    id__in=children_ids, school=school
                                )
                                parent.children.set(children)

                            # Send welcome email if requested
                            if send_welcome_email:
                                try:
                                    subject = f"Welcome to {school.name}"
                                    message = f"Hello {parent.user.first_name} {parent.user.last_name},\n\nYou have been registered as a parent at {school.name}."
                                    send_parent_email(parent, subject, message)
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to send welcome email to {parent.user.email}: {str(e)}"
                                    )

                            results["success"].append(
                                {
                                    "row": index + 2,
                                    "parent_id": parent.id,
                                    "email": parent.user.email,
                                    "name": f"{parent.user.first_name} {parent.user.last_name}",
                                }
                            )
                        else:
                            results["errors"].append(
                                {
                                    "row": index + 2,
                                    "email": parent_data.get("email", ""),
                                    "error": parent_serializer.errors,
                                }
                            )

                    except Exception as e:
                        results["errors"].append(
                            {
                                "row": index + 2,
                                "email": (
                                    parent_data.get("email", "")
                                    if "parent_data" in locals()
                                    else ""
                                ),
                                "error": str(e),
                            }
                        )

            if results["success"]:
                # Get the first successfully created parent
                first_parent = Parent.objects.get(id=results["success"][0]["parent_id"])
                log_action(
                    user=request.user,
                    action=f"Bulk imported {len(results['success'])} parents",
                    category=ActionCategory.CREATE,
                    obj=first_parent,
                    metadata={
                        "total_attempted": len(results["success"])
                        + len(results["errors"]),
                        "successful": len(results["success"]),
                        "failed": len(results["errors"]),
                        "default_status": default_status,
                        "send_welcome_email": send_welcome_email,
                    },
                )

            # FIXED: Always return 207 for bulk operations
            if not results.get("success") and results.get("errors"):
                return Response(
                    {
                        "error": "No valid records processed",
                        "success": [],
                        "errors": results["errors"],
                    },
                    status=status.HTTP_207_MULTI_STATUS,  # Changed from 400 to 207
                )

            return Response(results, status=status.HTTP_207_MULTI_STATUS)

        except Exception as e:
            logger.error(f"Bulk import failed: {str(e)}")
            return Response(
                {"error": f"Failed to process file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"], url_path="download-template")
    def download_template(self, request):
        # Create a workbook and add a worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Parents Template"

        # Add headers
        headers = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "address",
            "occupation",
            "children_ids",
            "preferred_language",
        ]
        ws.append(headers)

        # Add example row
        example_row = [
            "parent@example.com",
            "John",
            "Doe",
            "+254712345678",
            "123 Main St",
            "Engineer",
            "1,2,3",
            "en",
        ]
        ws.append(example_row)

        # Create response
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            "attachment; filename=parents_import_template.xlsx"
        )
        wb.save(response)

        return response

    def destroy(self, request, *args, **kwargs):
        parent = self.get_object()

        # Set current user for the delete signal to pick up
        User.set_current_user(request.user)

        # Let log_model_delete signal handle the logging
        return super().destroy(request, *args, **kwargs)


class ParentNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = ParentNotificationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "parent",
        "notification_type",
        "is_read",
        "related_student",
    ]

    def get_permissions(self):
        if self.action in ["create", "update", "destroy"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = ParentNotification.objects.all()
        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            return queryset

        # School admins can see notifications for parents in their school
        if hasattr(user, "school"):
            queryset = queryset.filter(parent__school=user.school)
        else:
            return ParentNotification.objects.none()

        # Parents can only see their own notifications
        if user.user_type == "parent":
            return queryset.filter(parent__user=user)

        # Teachers can see notifications for parents of their students
        if user.user_type == "teacher":
            student_ids = Student.objects.filter(
                Q(teacher=user.teacher_profile)
                | Q(school_class__teacher_assigned=user.teacher_profile)
            ).values_list("id", flat=True)
            return queryset.filter(related_student__in=student_ids)

        return queryset

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()

        log_action(
            user=request.user,
            action=f"Marked notification as read",
            category=ActionCategory.UPDATE,
            obj=notification.parent,
            metadata={
                "notification_id": notification.id,
                "message": (
                    notification.message[:50] + "..." if notification.message else None
                ),
            },
        )

        return Response({"status": "marked as read"})

    @action(detail=False, methods=["post"])
    def mark_all_as_read(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        queryset.update(is_read=True)
        return Response({"status": "all notifications marked as read"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        count = queryset.filter(is_read=False).count()
        return Response({"unread_count": count})


class ParentStatusChangeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ParentStatusChangeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "parent",
        "changed_by",
        "from_status",
        "to_status",
    ]

    def get_queryset(self):
        queryset = ParentStatusChange.objects.all()
        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            return queryset

        # School admins can see status changes for parents in their school
        if hasattr(user, "school"):
            queryset = queryset.filter(parent__school=user.school)
        else:
            return ParentStatusChange.objects.none()

        # Parents can only see their own status changes
        if user.user_type == "parent":
            return queryset.filter(parent__user=user)

        return queryset

    @action(detail=False, methods=["get"])
    def recent_activity(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        recent = queryset.order_by("-changed_at")[:10]
        serializer = self.get_serializer(recent, many=True)
        return Response(serializer.data)
