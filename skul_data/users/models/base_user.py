from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


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

    def __str__(self):
        return self.username
