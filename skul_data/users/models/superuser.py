from django.db import models
from .base_user import User


class SuperUser(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="superuser_profile"
    )
    school_name = models.CharField(max_length=250)
    school_code = models.CharField(max_length=50, unique=True)

    # Remove is_superuser - use user.is_superuser instead

    def __str__(self):
        return f"{self.user.username} - {self.school_name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            self.user.user_type = User.SCHOOL_SUPERUSER
            self.user.is_staff = True  # Give admin access
            self.user.is_superuser = True  # Give superuser privileges
            self.user.save()
        super().save(*args, **kwargs)


# class SuperUser(User):
#     school_name = models.CharField(max_length=250)
#     school_code = models.CharField(max_length=50, unique=True)
#     is_superuser = models.BooleanField(default=True)

#     def save(self, *args, **kwargs):
#         self.user_type = self.SCHOOL_SUPERUSER
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"{self.username} - {self.school_name}"
