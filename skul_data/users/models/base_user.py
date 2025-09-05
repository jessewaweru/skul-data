from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.deprecation import MiddlewareMixin
import uuid
from django.contrib.auth.models import BaseUserManager
from skul_data.users.models.role import Role


class CurrentUserMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            User.set_current_user(request.user)


class UserManager(BaseUserManager):
    def create_user(self, email, username=None, password=None, **extra_fields):
        """
        Create and save a User with the given email, username and password.
        """
        if not email:
            raise ValueError("Users must have an email address")

        if username is None:
            # Generate a username from email if not provided
            username = email.split("@")[0]

        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username=None, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email, username and password.
        Modified to handle the case where username is not provided (for pytest-django compatibility)
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, username, password, **extra_fields)


class User(AbstractUser):
    SCHOOL_ADMIN = "school_admin"
    ADMINISTRATOR = "administrator"
    TEACHER = "teacher"
    PARENT = "parent"
    OTHER = "other"

    USER_TYPE_CHOICES = [
        (SCHOOL_ADMIN, "School Administrator"),
        (ADMINISTRATOR, "Administrator"),
        (TEACHER, "Teacher"),
        (PARENT, "Parent"),
        (OTHER, "Other"),
    ]
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default=SCHOOL_ADMIN,
    )
    # Add a field to track if a teacher is also an administrator
    is_administrator = models.BooleanField(default=False)

    # Unique tracking ID for all users
    user_tag = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL)

    USERNAME_FIELD = "username"  # This is critical
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]  # Adjust as needed

    # Add this line to use our custom manager
    objects = UserManager()

    _current_user = None

    @classmethod
    def set_current_user(cls, user):
        cls._current_user = user

    @classmethod
    def get_current_user(cls):
        return cls._current_user

    def save(self, *args, **kwargs):
        """
        Override save method to track changed fields.
        Uses *args, **kwargs as expected in Django model save methods.
        """
        # Track changed fields
        if self.pk:
            try:
                old = User.objects.get(pk=self.pk)
                self._changed_fields = [
                    field.name
                    for field in self._meta.fields
                    if getattr(old, field.name) != getattr(self, field.name)
                ]
            except User.DoesNotExist:
                # If the user is new, there won't be any changed fields
                self._changed_fields = []

        # Call the parent save method with *args, **kwargs
        super().save(*args, **kwargs)

    # @property
    # def school(self):
    #     """Returns the school associated with this user based on their role."""
    #     if hasattr(self, "school_admin_profile"):
    #         return self.school_admin_profile.school
    #     elif hasattr(self, "teacher_profile"):
    #         return self.teacher_profile.school
    #     elif hasattr(self, "parent_profile"):
    #         return self.parent_profile.school
    #     return None

    @property
    def school(self):
        """Returns the school associated with this user"""
        # Check all possible profile relationships
        profiles = [
            getattr(self, "school_admin_profile", None),
            getattr(self, "teacher_profile", None),
            getattr(self, "parent_profile", None),
            getattr(self, "administrator_profile", None),
        ]

        # Return the first valid school found
        for profile in profiles:
            if profile and profile.school:
                return profile.school

        return None  # Explicit return if no school found

    @property
    def primary_profile(self):
        """Returns the user's primary profile object."""
        if hasattr(self, "school_admin_profile"):
            return self.school_admin_profile
        elif hasattr(self, "teacher_profile"):
            return self.teacher_profile
        elif hasattr(self, "parent_profile"):
            return self.parent_profile
        return None

    # Add this method to check permissions
    def has_perm(self, perm, obj=None):
        if self.user_type == self.SCHOOL_ADMIN:
            return True
        if self.role and self.role.permissions.filter(code=perm).exists():
            return True
        return super().has_perm(perm, obj)

    def get_username(self):
        return self.email  # Or your username field

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        return self.first_name

    def __str__(self):
        return self.username


from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class CustomUserModelBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in using either username or email.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        if username is None or password is None:
            return None

        try:
            # Try to find user by username or email
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except User.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
