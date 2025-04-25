from django.db import models
from .base_user import User
from django.utils import timezone
from skul_data.users.utils.parent import send_parent_email


class Parent(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("PENDING", "Pending Approval"),
        ("SUSPENDED", "Suspended"),
        ("INACTIVE", "Inactive"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="parent_profile"
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="parents"
    )
    children = models.ManyToManyField("students.Student", related_name="parents")
    address = models.TextField(blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    preferred_language = models.CharField(max_length=10, default="en")
    receive_email_notifications = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - Parent"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only set user_type on creation
            self.user.user_type = User.PARENT
            self.user.save()
        super().save(*args, **kwargs)

    def send_notification(
        self, message, notification_type, related_student=None, sender=None
    ):
        """Helper method to create and send a notification"""
        notification = ParentNotification.objects.create(
            parent=self,
            message=message,
            notification_type=notification_type,
            related_student=related_student,
            sent_by=sender,
        )

        # Send actual notification based on preferences
        if self.receive_email_notifications:
            send_parent_email(self, "New Notification", message)

        return notification

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email

    @property
    def active_children(self):
        return self.children.filter(status="ACTIVE")

    @property
    def children_count(self):
        return self.children.count()

    class Meta:
        ordering = ["user__last_name", "user__first_name"]


class ParentStatusChange(models.Model):
    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name="status_changes"
    )
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    from_status = models.CharField(max_length=20, choices=Parent.STATUS_CHOICES)
    to_status = models.CharField(max_length=20, choices=Parent.STATUS_CHOICES)
    reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return (
            f"{self.parent} status changed from {self.from_status} to {self.to_status}"
        )


class ParentNotification(models.Model):
    NOTIFICATION_TYPES = [
        ("ACADEMIC", "Academic Update"),
        ("ATTENDANCE", "Attendance Alert"),
        ("BEHAVIOR", "Behavior Notification"),
        ("EVENT", "Event Reminder"),
        ("MANUAL", "Manual Message"),
        ("SYSTEM", "System Notification"),
    ]

    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    related_student = models.ForeignKey(
        "students.Student", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.parent}"
