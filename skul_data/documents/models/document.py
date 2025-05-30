import uuid
import os
from django.db import models
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.base_user import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation


class DocumentCategory(models.Model):
    name = models.CharField(max_length=255)  # Removed unique=True
    description = models.TextField(blank=True, null=True)
    is_custom = models.BooleanField(
        default=False
    )  # True if added by school, False if predefined
    school = models.ForeignKey(
        "schools.School", null=True, blank=True, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            "name",
            "school",
        )  # Prevent duplicate category names per school
        verbose_name_plural = "Document Categories"

    def __str__(self):
        return f"{self.name} ({self.school.name if self.school else 'System'})"

    def clean(self):
        # Custom validation logic
        if self.is_custom and not self.school:
            raise ValidationError(
                {"school": "Custom categories must be associated with a school"}
            )

        # Check for name uniqueness within school context
        if self.school:
            qs = DocumentCategory.objects.filter(name=self.name, school=self.school)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"name": "A category with this name already exists for this school"}
                )

    def save(self, *args, **kwargs):
        # System categories must have school=None
        if not self.is_custom and self.school:
            raise ValidationError(
                "System categories cannot be associated with a school"
            )
        # Custom categories must have a school
        if self.is_custom and not self.school:
            raise ValidationError("Custom categories must be associated with a school")
        super().save(*args, **kwargs)


def document_upload_path(instance, filename):
    """Dynamic upload path: documents/school_id/category/filename"""
    school_id = instance.school.id if instance.school else "system"
    category = instance.category.name.replace(" ", "_").lower()
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"documents/{school_id}/{category}/{filename}"


class Document(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to=document_upload_path)
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)
    related_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional: Class this document is associated with",
    )
    related_students = models.ManyToManyField(
        "students.Student",
        blank=True,
        help_text="Optional: Students this document is associated with",
    )
    actions = GenericRelation(
        "action_logs.ActionLog",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="document",
    )

    # Uploader information
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Access control
    is_public = models.BooleanField(default=False)
    allowed_roles = models.ManyToManyField(
        "users.Role", blank=True, help_text="Roles that can access this document"
    )
    allowed_users = models.ManyToManyField(
        User,
        related_name="allowed_documents",
        blank=True,
        help_text="Specific users who can access this document",
    )

    # Metadata
    file_size = models.PositiveIntegerField(editable=False, default=0)
    file_type = models.CharField(max_length=50, editable=False, default="")

    class Meta:
        ordering = ["-uploaded_at"]
        permissions = [
            ("bulk_delete_document", "Can bulk delete documents"),
            ("bulk_download_document", "Can bulk download documents"),
        ]

    def __str__(self):
        return f"{self.title} - {self.school.name if self.school else 'System'}"

    def clean(self):
        # Validate file size (10MB limit)
        if self.file.size > 10 * 1024 * 1024:
            raise ValidationError("File size cannot exceed 10MB")

        # Validate file types
        valid_extensions = [
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".jpg",
            ".jpeg",
            ".png",
            ".csv",
        ]
        ext = os.path.splitext(self.file.name)[1].lower()
        if ext not in valid_extensions:
            raise ValidationError("Unsupported file type")

    def save(self, *args, **kwargs):
        # Set file metadata
        if not self.pk and self.file:
            self.file_size = self.file.size
            self.file_type = os.path.splitext(self.file.name)[1].lower()

            # Set school from uploader if not set
            if not self.school:
                if hasattr(self.uploaded_by, "teacher_profile"):
                    self.school = self.uploaded_by.teacher_profile.school
                elif hasattr(self.uploaded_by, "schooladmin_profile"):
                    self.school = self.uploaded_by.schooladmin_profile.school

        super().save(*args, **kwargs)

    def __str__(self):
        uploader = self.uploaded_by_schooladmin or self.uploaded_by_teacher
        return f"{self.title} uploaded by {uploader}"


class DocumentShareLink(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    password = models.CharField(max_length=128, blank=True, null=True)
    download_limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="Optional: Limit number of downloads"
    )
    download_count = models.PositiveIntegerField(default=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track original values for change detection
        self._original_download_count = self.download_count

    def save(self, *args, **kwargs):
        # Track field changes
        changed_fields = []
        if self.pk:  # Only for existing objects
            if self.download_count != self._original_download_count:
                changed_fields.append("download_count")
                if self.download_count > self._original_download_count:
                    self._download_increment = True

        self._changed_fields = changed_fields
        super().save(*args, **kwargs)

        # Update original values after save
        self._original_download_count = self.download_count

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.is_expired() and (
            self.download_limit is None or self.download_count < self.download_limit
        )

    def __str__(self):
        return f"Share link for {self.document.title} (expires: {self.expires_at})"
