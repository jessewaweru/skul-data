from django.db import models
from .base_user import User


class Teacher(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="teacher_profile"
    )
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="teachers"
    )
    subjects_taught = models.CharField(max_length=255, blank=True, null=True)
    assigned_class = models.OneToOneField(
        "schools.SchoolClass",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_assigned",
    )

    def __str__(self):
        return f"{self.user.username} - {self.school.name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            self.user.user_type = User.TEACHER
            self.user.save()
        super().save(*args, **kwargs)


# class Teacher(User):
#     school = models.ForeignKey("schools.School", on_delete=models.CASCADE)
#     subjects_taught = models.CharField(max_length=255, blank=True, null=True)
#     assigned_class = models.OneToOneField(
#         "schools.SchoolClass", on_delete=models.SET_NULL, null=True, blank=True
#     )

#     def save(self, *args, **kwargs):
#         self.user_type = self.TEACHER
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"{self.username}{self.school.name}"
