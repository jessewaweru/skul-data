import os
import io
import zipfile
from django.core.files.base import ContentFile
from django.http import FileResponse
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


class DocumentCategoryViewSet(viewsets.ModelViewSet):
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["school", "is_custom"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_authenticated:
            if user.user_type == User.SCHOOL_SUPERUSER:
                return queryset.filter(school=user.superuser_profile.school)
            elif user.user_type == User.TEACHER:
                return queryset.filter(school=user.teacher_profile.school)

        return queryset.filter(is_custom=False)

    def perform_create(self, serializer):
        user = self.request.user
        school = None

        if user.user_type == User.SCHOOL_SUPERUSER:
            school = user.superuser_profile.school
        elif user.user_type == User.TEACHER:
            school = user.teacher_profile.school

        serializer.save(school=school, is_custom=True)


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

        # Superusers see all documents in their school
        if user.user_type == User.SCHOOL_SUPERUSER:
            return queryset.filter(school=user.superuser_profile.school)
        # Teachers see documents for their school and assigned classes
        if user.user_type == User.TEACHER:
            teacher_profile = user.teacher_profile
            return queryset.filter(school=teacher_profile.school).filter(
                models.Q(related_class__isnull=True)
                | models.Q(related_class=teacher_profile.assigned_class)
            )
        # Parents see documents for their children
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
        serializer.save(uploaded_by=self.request.user)

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

        serializer = self.get_serializer(uploaded_docs, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def generate_share_link(self, request, pk=None):
        document = self.get_object()
        serializer = DocumentShareLinkSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save(document=document, created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def bulk_download(self, request):
        document_ids = request.query_params.getlist("ids")
        documents = self.get_queryset().filter(id__in=document_ids)

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


class DocumentShareLinkViewSet(viewsets.ModelViewSet):
    queryset = DocumentShareLink.objects.all()
    serializer_class = DocumentShareLinkSerializer

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        share_link = self.get_object()

        if not share_link.is_valid():
            return Response(
                {
                    "detail": "This share link is expired or has reached its download limit"
                },
                status=status.HTTP_410_GONE,
            )

        # Check password if set
        password = request.query_params.get("password")
        if share_link.password and share_link.password != password:
            return Response(
                {"detail": "Invalid password"}, status=status.HTTP_403_FORBIDDEN
            )

        # Increment download count
        share_link.download_count += 1
        share_link.save()

        document = share_link.document
        if not document.file:
            raise Http404("Document file not found")

        response = FileResponse(document.file.open("rb"))
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(document.file.name)}"'
        )
        return response
