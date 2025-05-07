from django.db import models
from django.contrib.auth.models import Permission


class Permission(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Role(models.Model):
    ROLE_TYPES = [
        ("SYSTEM", "System Defined"),
        ("CUSTOM", "Custom"),
    ]

    name = models.CharField(max_length=100)
    role_type = models.CharField(max_length=10, choices=ROLE_TYPES, default="CUSTOM")
    permissions = models.ManyToManyField(Permission)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="roles"
    )

    class Meta:
        unique_together = ("name", "school")

    def __str__(self):
        return f"{self.name} ({self.school.name})"
