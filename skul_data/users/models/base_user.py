from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from skul_data.users.models.role import Role


class User(AbstractUser):
    SCHOOL_SUPERUSER = "school_superuser"
    TEACHER = "teacher"
    PARENT = "parent"
    OTHER = "other"

    USER_TYPE_CHOICES = [
        (SCHOOL_SUPERUSER, "School Superuser"),
        (TEACHER, "Teacher"),
        (PARENT, "Parent"),
        (OTHER, "Other"),
    ]
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default=SCHOOL_SUPERUSER,
    )
    # Unique tracking ID for all users
    user_tag = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    # Add this method to check permissions
    def has_perm(self, perm, obj=None):
        if self.is_superuser:
            return True
        if self.role and self.role.permissions.filter(codename=perm).exists():
            return True
        return super().has_perm(perm, obj)

    def __str__(self):
        return self.username
