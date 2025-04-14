from django.db import models
from django.contrib.auth.models import Permission


class Role(models.Model):
    ROLE_TYPES = [
        ("SYSTEM", "System Defined"),
        ("CUSTOM", "Custom"),
    ]

    name = models.CharField(max_length=100, unique=True)
    role_type = models.CharField(max_length=10, choices=ROLE_TYPES, default="CUSTOM")
    permissions = models.ManyToManyField(Permission)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="roles"
    )

    class Meta:
        permissions = [
            ("manage_roles", "Can create, edit and delete roles"),
        ]

    def __str__(self):
        return f"{self.name} ({self.school.name})"
