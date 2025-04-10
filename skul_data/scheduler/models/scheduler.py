from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class SchoolEvent(models.Model):
    EVENT_TYPES = [
        ("general", "General"),
        ("meeting", "Meeting"),
        ("exam", "Exam"),
        ("holiday", "Holiday"),
        ("announcement", "Announcement"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default="general")

    # Who created the event (usually the superuser)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_events"
    )

    # Specific target users
    targeted_teachers = models.ManyToManyField(
        User, blank=True, related_name="teacher_events"
    )
    targeted_parents = models.ManyToManyField(
        User, blank=True, related_name="parent_events"
    )

    # Optional tags
    is_for_all_teachers = models.BooleanField(default=False)
    is_for_all_parents = models.BooleanField(default=False)

    attachment = models.FileField(upload_to="event_attachments/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
