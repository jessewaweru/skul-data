from django.db import models
from skul_data.users.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone


class ActionCategory(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    VIEW = "VIEW", "View"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    UPLOAD = "UPLOAD", "Upload"
    DOWNLOAD = "DOWNLOAD", "Download"
    SHARE = "SHARE", "Share"
    SYSTEM = "SYSTEM", "System"
    OTHER = "OTHER", "Other"


class ActionLog(models.Model):
    # User who performed the action
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="actions"
    )
    user_tag = models.UUIDField(editable=False)

    # Action details
    action = models.CharField(max_length=255)
    category = models.CharField(
        max_length=20, choices=ActionCategory.choices, default=ActionCategory.OTHER
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, null=True)

    # Affected model/object (using generic foreign key)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # Additional context
    metadata = models.JSONField(default=dict, blank=True)
    # timestamp = models.DateTimeField(auto_now_add=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["user"]),
            models.Index(fields=["category"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        verbose_name = "Action Log"
        verbose_name_plural = "Action Logs"

    def __str__(self):
        return f"{self.user_tag} - {self.get_category_display()} - {self.action}"

    def save(self, *args, **kwargs):
        if self.user and not self.user_tag:
            self.user_tag = self.user.user_tag
        super().save(*args, **kwargs)

    @property
    def affected_model(self):
        if self.content_type:
            return self.content_type.model_class().__name__
        return None

    @property
    def affected_object(self):
        if self.content_object:
            return str(self.content_object)
        return None
