from django.db import models
from django.conf import settings
from skul_data.students.models.student import Student
from skul_data.users.models.superuser import SuperUser


class School(models.Model):
    name = models.CharField(max_length=255, unique=True)
    level = models.CharField(max_length=50, default="Primary")
    code = models.CharField(max_length=20, unique=True, default="SKUD000")
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15, default="0700000000")
    superuser_profile = models.OneToOneField(
        SuperUser, on_delete=models.CASCADE, null=True, blank=True
    )
    created_by = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="school"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
