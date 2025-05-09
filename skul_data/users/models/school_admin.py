from django.db import models
from .base_user import User
from skul_data.schools.models.school import School


class SchoolAdmin(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="school_admin_profile"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="administrators"
    )
    is_primary = models.BooleanField(default=True)

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
