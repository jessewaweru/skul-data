from rest_framework import serializers
from skul_data.documents.models.document import (
    Document,
    DocumentCategory,
    DocumentShareLink,
)
from skul_data.users.models import User
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta


class DocumentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentCategory
        fields = ["id", "name", "description", "is_custom", "created_at"]
        read_only_fields = ["is_custom", "created_at"]


class DocumentSerializer(serializers.ModelSerializer):
    category = DocumentCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=DocumentCategory.objects.all(), source="category", write_only=True
    )
    school_name = serializers.CharField(source="school.name", read_only=True)
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.get_full_name", read_only=True
    )
    file_url = serializers.SerializerMethodField()
    file_type = serializers.CharField(read_only=True)
    file_size = serializers.CharField(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "file",
            "file_url",
            "file_type",
            "file_size",
            "category",
            "category_id",
            "school",
            "school_name",
            "related_class",
            "related_students",
            "uploaded_by",
            "uploaded_by_name",
            "uploaded_at",
            "is_public",
            "allowed_roles",
            "allowed_users",
        ]
        read_only_fields = ["uploaded_by", "uploaded_at", "file_type", "file_size"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def validate(self, data):
        user = self.context["request"].user
        school = data.get("school")

        # Validate school permissions
        if school:
            if user.user_type == User.TEACHER and user.teacher_profile.school != school:
                raise PermissionDenied("You can only upload documents for your school")
            elif (
                user.user_type == User.SCHOOL_SUPERUSER
                and user.superuser_profile.school != school
            ):
                raise PermissionDenied("You can only upload documents for your school")

        return data


class DocumentShareLinkSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)
    document_url = serializers.SerializerMethodField()
    expires_in = serializers.SerializerMethodField()

    class Meta:
        model = DocumentShareLink
        fields = [
            "id",
            "document",
            "document_title",
            "document_url",
            "token",
            "expires_at",
            "expires_in",
            "password",
            "download_limit",
            "download_count",
            "created_at",
        ]
        read_only_fields = ["token", "download_count", "created_at"]

    def get_document_url(self, obj):
        request = self.context.get("request")
        if obj.document.file and request:
            return request.build_absolute_uri(obj.document.file.url)
        return None

    def get_expires_in(self, obj):
        return (obj.expires_at - timezone.now()).days if obj.expires_at else None

    def validate(self, data):
        # Set default expiration (7 days from now)
        if not data.get("expires_at"):
            data["expires_at"] = timezone.now() + timedelta(days=7)
        return data
