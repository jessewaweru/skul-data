from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.deprecation import MiddlewareMixin
import uuid
from skul_data.users.models.role import Role


class CurrentUserMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            User.set_current_user(request.user)


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

    _current_user = None

    @classmethod
    def set_current_user(cls, user):
        cls._current_user = user

    @classmethod
    def get_current_user(cls):
        return cls._current_user

    def save(self, *args, **kwargs):
        # Track changed fields
        if self.pk:
            old = User.objects.get(pk=self.pk)
            self._changed_fields = [
                field.name
                for field in self._meta.fields
                if getattr(old, field.name) != getattr(self, field.name)
            ]
        super().save(*args, **kwargs)

    # Add this method to check permissions
    def has_perm(self, perm, obj=None):
        if self.is_superuser:
            return True
        if self.role and self.role.permissions.filter(codename=perm).exists():
            return True
        return super().has_perm(perm, obj)

    def __str__(self):
        return self.username
