from django.db import models
from skul_data.users.models.parent import Parent
from skul_data.users.models.superuser import SuperUser
from skul_data.users.models.teacher import Teacher


class Actionlog(models.Model):
    #  track user activity by recording each action performed
    action_by_superuser = models.ForeignKey(
        SuperUser, on_delete=models.CASCADE, null=True, blank=True
    )
    action_by_teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, null=True, blank=True
    )
    action_by_parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, null=True, blank=True
    )
    user_tag = models.UUIDField()
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.user_tag:
            self.user_tag = self.user.user_tag  # Ensure it's always linked
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_tag} - {self.action} at {self.timestamp}"
