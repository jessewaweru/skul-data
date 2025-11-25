from django.db import models
from django.utils import timezone
from datetime import date
from skul_data.users.models.base_user import User
from skul_data.schools.models.school import School


class SchoolAdmin(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="school_admin_profile"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="primary_admins"
    )
    is_primary = models.BooleanField(default=True)
    signature = models.ImageField(
        upload_to="signatures/staff/",
        null=True,
        blank=True,
        help_text="User's signature image",
    )

    class Meta:
        verbose_name = "School Administrator"
        verbose_name_plural = "School Administrators"

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.school.name}"

    def save(self, *args, **kwargs):
        # Check if this admin is being set as primary
        if self.is_primary:
            # Get existing primary admin for this school (if any)
            try:
                current_primary = SchoolAdmin.objects.get(
                    school=self.school, is_primary=True
                )
                # If this isn't the same admin and there's a current primary,
                # update the current primary to not be primary
                if current_primary.pk != getattr(self, "pk", None):
                    current_primary.is_primary = False
                    current_primary.save(update_fields=["is_primary"])
            except SchoolAdmin.DoesNotExist:
                pass  # No existing primary admin

        super().save(*args, **kwargs)


class AdministratorProfile(models.Model):
    ACCESS_LEVEL_CHOICES = [
        ("standard", "Standard Access"),
        ("elevated", "Elevated Access"),
        ("restricted", "Restricted Access"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="administrator_profile"
    )
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="admin_profiles"
    )
    position = models.CharField(max_length=100)
    access_level = models.CharField(
        max_length=20, choices=ACCESS_LEVEL_CHOICES, default="standard"
    )
    is_active = models.BooleanField(default=True)
    date_appointed = models.DateField(default=date.today)
    permissions_granted = models.JSONField(default=list)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    signature = models.ImageField(
        upload_to="signatures/staff/",
        null=True,
        blank=True,
        help_text="User's signature image",
    )

    class Meta:
        ordering = ["-date_appointed"]
        verbose_name = "Administrator Profile"
        verbose_name_plural = "Administrator Profiles"

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.position}"

    def save(self, *args, **kwargs):
        # Track changed fields for updates
        if self.pk:
            try:
                old = AdministratorProfile.objects.get(pk=self.pk)
                self._changed_fields = [
                    field.name
                    for field in self._meta.fields
                    if getattr(old, field.name) != getattr(self, field.name)
                ]
            except AdministratorProfile.DoesNotExist:
                self._changed_fields = []
        else:
            # For new instances, set user type
            self.user.user_type = User.ADMINISTRATOR
            self.user.save()

        super().save(*args, **kwargs)
