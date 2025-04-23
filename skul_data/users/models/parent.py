from django.db import models
from .base_user import User


class Parent(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="parent_profile"
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="parents"
    )
    children = models.ManyToManyField("students.Student", related_name="parents")

    def __str__(self):
        return f"{self.user.username} - Parent"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only set user_type on creation
            self.user.user_type = User.PARENT
            self.user.save()
        super().save(*args, **kwargs)


# class Parent(models.Model):
#     name = models.CharField(max_length=100)
#     email = models.EmailField(unique=True)
#     phone_number = models.CharField(max_length=15, blank=True, null=True)
#     school = models.ForeignKey("schools.School", on_delete=models.CASCADE)
#     children = models.ManyToManyField("students.Student", related_name="parents")

#     def __str__(self):
#         return f"{self.user.username} - Parent"

#     def save(self, *args, **kwargs):
#         self.user.user_type = User.PARENT
#         self.user.save()
#         super().save(*args, **kwargs)
