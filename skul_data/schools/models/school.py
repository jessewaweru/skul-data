from django.db import models
from django.conf import settings
from skul_data.students.models.student import Student
import random


class School(models.Model):
    SCHOOL_TYPES = [
        ("PRE", "Pre-school"),
        ("PRI", "Primary"),
        ("SEC", "Secondary"),
        ("HS", "High School"),
    ]

    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=3, choices=SCHOOL_TYPES, default="PRI")
    motto = models.CharField(max_length=255, blank=True)
    founded_date = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, default="Kenya")
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField()
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="school_logos/", null=True, blank=True)
    timezone = models.CharField(max_length=50, default="Africa/Nairobi")

    # Academic Structure
    academic_year_structure = models.CharField(
        max_length=20,
        choices=[("SEMESTER", "Semester"), ("TERM", "Term"), ("QUARTER", "Quarter")],
        default="TERM",
    )

    # Relationships
    schooladmin = models.OneToOneField(
        "users.User",
        on_delete=models.PROTECT,
        related_name="administered_school",
        default=None,
    )

    # Status
    is_active = models.BooleanField(default=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("manage_school", "Can manage all school operations"),
            ("view_dashboard", "Can view school dashboard"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"{self.name[:3].upper()}{random.randint(100,999)}"
        super().save(*args, **kwargs)
