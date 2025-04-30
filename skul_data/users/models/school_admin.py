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
        if not self.pk:  # On creation
            # Ensure only one primary admin per school
            if self.is_primary:
                SchoolAdmin.objects.filter(school=self.school, is_primary=True).update(
                    is_primary=False
                )
        super().save(*args, **kwargs)
