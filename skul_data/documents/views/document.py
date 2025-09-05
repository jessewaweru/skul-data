import os
import io
import zipfile
from django.db import models
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework import viewsets
from skul_data.documents.models.document import DocumentCategory
from skul_data.documents.serializers.document import (
    DocumentCategorySerializer,
)
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.users.models.base_user import User
from skul_data.documents.models.document import Document
from skul_data.documents.permissions.permission import (
    CanUploadDocument,
    CanViewDocument,
    CanManageDocument,
)
from skul_data.documents.serializers.document import DocumentSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from skul_data.documents.serializers.document import (
    DocumentShareLinkSerializer,
    DocumentShareLink,
)
from skul_data.action_logs.signals.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory


class DocumentCategoryViewSet(viewsets.ModelViewSet):
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["school", "is_custom"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_authenticated:
            if user.user_type == User.SCHOOL_ADMIN:
                # Include both school-specific categories and system categories (school=None)
                return queryset.filter(
                    models.Q(school=user.school_admin_profile.school)
                    | models.Q(school=None)
                )
            elif user.user_type == User.TEACHER:
                # Include both school-specific categories and system categories (school=None)
                return queryset.filter(
                    models.Q(school=user.teacher_profile.school) | models.Q(school=None)
                )

        return queryset.filter(is_custom=False)

    def perform_create(self, serializer):
        user = self.request.user
        school = None

        if user.user_type == User.SCHOOL_ADMIN:
            school = user.school_admin_profile.school
        elif user.user_type == User.TEACHER:
            school = user.teacher_profile.school

        serializer.save(school=school, is_custom=True)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_custom:
            return Response(
                {"detail": "System categories cannot be modified"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "school",
        "category",
        "related_class",
        "uploaded_by",
        "is_public",
        "is_template",
    ]

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [CanManageDocument()]  # e.g. Only school admins
        if self.action in ["retrieve", "list"]:
            return [CanViewDocument()]  # e.g. Teachers, parents, etc.
        return [CanUploadDocument()]  # For create/bulk_upload

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return queryset.none()

        # School admins see all documents in their school
        if user.user_type == User.SCHOOL_ADMIN:
            return queryset.filter(school=user.school_admin_profile.school)

        # Teachers see:
        # 1. Public documents from their school
        # 2. Documents for their assigned class
        # 3. Documents they uploaded
        if user.user_type == User.TEACHER:
            teacher_profile = user.teacher_profile
            school = teacher_profile.school

            return queryset.filter(
                models.Q(school=school)
                & (
                    models.Q(is_public=True)  # Public docs
                    | models.Q(
                        related_class=teacher_profile.assigned_class
                    )  # Class docs
                    | models.Q(uploaded_by=user)  # Own docs
                )
            ).distinct()

        # Parents see documents for their children and public documents
        if user.user_type == User.PARENT:
            parent_profile = user.parent_profile
            return queryset.filter(
                models.Q(school=parent_profile.school)
                & (
                    models.Q(related_students__in=parent_profile.children.all())
                    | models.Q(is_public=True)
                )
            ).distinct()

        return queryset.none()

    def perform_create(self, serializer):
        # Set user context for signal
        instance = serializer.save(uploaded_by=self.request.user)
        instance._current_user = self.request.user

        # Manual log for additional context
        log_action(
            user=self.request.user,
            action=f"Uploaded document: {instance.title}",
            category=ActionCategory.UPLOAD,
            obj=instance,
            metadata={
                "file_size": instance.file_size,
                "file_type": instance.file_type,
                "category": instance.category.name if instance.category else None,
            },
        )

    def perform_update(self, serializer):
        """Log document updates"""
        # Get the old instance for comparison
        old_instance = self.get_object()
        old_title = old_instance.title

        # Save the updated instance
        instance = serializer.save()
        instance._current_user = self.request.user

        # Prepare change tracking
        changes = {}
        if hasattr(serializer, "validated_data"):
            for field, new_value in serializer.validated_data.items():
                old_value = getattr(old_instance, field, None)
                if old_value != new_value:
                    changes[field] = {
                        "old": str(old_value) if old_value is not None else None,
                        "new": str(new_value) if new_value is not None else None,
                    }

        # Manual log for document update
        log_action(
            user=self.request.user,
            action=f"Updated Document",  # This matches your test expectation
            category=ActionCategory.UPDATE,
            obj=instance,
            metadata={
                "changes": changes,
                "previous_title": old_title,
                "current_title": instance.title,
            },
        )

    @action(detail=False, methods=["post"])
    def bulk_upload(self, request):
        files = request.FILES.getlist("files")
        zip_file = request.FILES.get("zip")

        school = request.data.get("school")  # Optional: you can require this
        category = request.data.get("category")
        related_class = request.data.get("related_class")
        is_public = request.data.get("is_public", "false").lower() == "true"

        uploaded_docs = []

        # If a ZIP file was uploaded
        if zip_file:
            with zipfile.ZipFile(zip_file) as zip_ref:
                for filename in zip_ref.namelist():
                    if filename.endswith("/"):  # Skip directories
                        continue
                    file_data = zip_ref.read(filename)
                    content_file = ContentFile(
                        file_data, name=os.path.basename(filename)
                    )

                    doc = Document.objects.create(
                        school_id=school,
                        category_id=category,
                        related_class_id=related_class,
                        is_public=is_public,
                        uploaded_by=request.user,
                        file=content_file,
                    )
                    uploaded_docs.append(doc)

        elif files:
            for f in files:
                doc = Document.objects.create(
                    school_id=school,
                    category_id=category,
                    related_class_id=related_class,
                    is_public=is_public,
                    uploaded_by=request.user,
                    file=f,
                )
                uploaded_docs.append(doc)
        else:
            return Response(
                {"detail": "No valid files provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Log the bulk operation
        log_action(
            user=request.user,
            action=f"Bulk uploaded {len(uploaded_docs)} documents",
            category=ActionCategory.UPLOAD,
            metadata={
                "document_count": len(uploaded_docs),
                "document_ids": [doc.id for doc in uploaded_docs],
                "category": category,
                "is_zip": bool(zip_file),
            },
        )

        serializer = self.get_serializer(uploaded_docs, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def generate_share_link(self, request, pk=None):
        document = self.get_object()
        # Add the document ID to the request data
        data = (
            request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        )
        data["document"] = document.id
        serializer = DocumentShareLinkSerializer(
            data=data, context={"request": request}
        )
        # if serializer.is_valid():
        #     serializer.save(created_by=request.user)
        #     return Response(serializer.data, status=status.HTTP_201_CREATED)

        # print(f"Serializer errors: {serializer.errors}")
        # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if serializer.is_valid():
            share_link = serializer.save(created_by=request.user)
            share_link._current_user = request.user  # For potential signals

            # Manual logging
            log_action(
                user=request.user,
                action=f"Generated share link for: {document.title}",
                category=ActionCategory.SHARE,
                obj=share_link,
                metadata={
                    "document_id": document.id,
                    "expires_at": share_link.expires_at.isoformat(),
                    "has_password": bool(share_link.password),
                },
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def bulk_download(self, request):
        # Get the 'ids' parameter - might be a list or a single comma-separated string
        ids_param = request.query_params.get("ids", "")
        # Handle different ways the ids might be provided
        if isinstance(ids_param, str) and "," in ids_param:
            # Split the comma-separated string into a list of integers
            document_ids = [
                int(id_str.strip()) for id_str in ids_param.split(",") if id_str.strip()
            ]
        else:
            # Handle case when ids are provided as multiple parameters
            document_ids = request.query_params.getlist("ids")

        documents = self.get_queryset().filter(id__in=document_ids)

        if documents.exists():
            log_action(
                user=request.user,
                action=f"Bulk downloaded {documents.count()} documents",
                category=ActionCategory.DOWNLOAD,
                metadata={
                    "document_count": documents.count(),
                    "document_ids": list(documents.values_list("id", flat=True)),
                    "document_titles": list(
                        documents.values_list("title", flat=True)[:10]
                    ),  # First 10 titles
                },
            )

        if not documents.exists():
            return Response(
                {"detail": "No valid documents selected"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Create a ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for doc in documents:
                if doc.file:
                    file_path = doc.file.path
                    if os.path.exists(file_path):
                        zip_file.write(file_path, os.path.basename(file_path))

        zip_buffer.seek(0)
        response = FileResponse(zip_buffer, content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="documents.zip"'
        return response

    @action(detail=False)
    def shared_with_me(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            allowed_users=request.user
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class DocumentShareLinkViewSet(viewsets.ModelViewSet):
    queryset = DocumentShareLink.objects.all()
    serializer_class = DocumentShareLinkSerializer

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user)

    def perform_create(self, serializer):
        """Ensure current user is set when creating share links"""
        instance = serializer.save(created_by=self.request.user)
        instance._current_user = self.request.user
        return instance

    @action(detail=False, methods=["get"], url_path="download/(?P<token>[^/.]+)")
    def download(self, request, token=None):
        try:
            share_link = DocumentShareLink.objects.get(token=token)
        except DocumentShareLink.DoesNotExist:
            # Log failed access attempt
            log_action(
                user=None,  # Anonymous access
                action=f"Failed share link access - invalid token: {token}",
                category=ActionCategory.OTHER,
                metadata={
                    "ip_address": self.get_client_ip(request),
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
                    "token": str(token)[:8] + "...",  # Partial token for security
                },
            )
            return Response(
                {"detail": "Share link not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not share_link.is_valid():
            log_action(
                user=share_link.created_by,  # Link creator for context
                action=f"Expired/invalid share link accessed: {share_link.document.title}",
                category=ActionCategory.OTHER,
                obj=share_link,
                metadata={
                    "ip_address": self.get_client_ip(request),
                    "is_expired": share_link.is_expired(),
                    "download_count": share_link.download_count,
                    "download_limit": share_link.download_limit,
                },
            )
            return Response(
                {
                    "detail": "This share link is expired or has reached its download limit"
                },
                status=status.HTTP_410_GONE,
            )

        # Check password if set
        password = request.query_params.get("password")
        if share_link.password and share_link.password != password:
            log_action(
                user=share_link.created_by,
                action=f"Failed password attempt for share link: {share_link.document.title}",
                category=ActionCategory.OTHER,
                obj=share_link,
                metadata={
                    "ip_address": self.get_client_ip(request),
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
                },
            )
            return Response(
                {"detail": "Invalid password"}, status=status.HTTP_403_FORBIDDEN
            )

        # Increment download count with proper tracking
        share_link._current_user = share_link.created_by
        share_link.download_count += 1
        share_link._download_increment = True
        share_link.save()

        document = share_link.document
        if not document.file:
            raise Http404("Document file not found")

        response = FileResponse(document.file.open("rb"))
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(document.file.name)}"'
        )
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        return (
            x_forwarded_for.split(",")[0]
            if x_forwarded_for
            else request.META.get("REMOTE_ADDR")
        )
