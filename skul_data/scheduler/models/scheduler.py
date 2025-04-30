from django.db import models
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.utils import timezone
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent

User = get_user_model()


class SchoolEvent(models.Model):
    EVENT_TYPES = [
        ("general", "General"),
        ("meeting", "Meeting"),
        ("exam", "Exam"),
        ("holiday", "Holiday"),
        ("announcement", "Announcement"),
        ("parent_event", "Parent Event"),
        ("staff_event", "Staff Event"),
    ]

    EVENT_TARGETS = [
        ("all", "Everyone"),
        ("teachers", "Teachers"),
        ("parents", "Parents"),
        ("specific", "Specific Users"),
        ("classes", "Specific Classes"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default="general")
    target_type = models.CharField(max_length=20, choices=EVENT_TARGETS, default="all")

    # Who created the event (usually the superuser)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_events"
    )
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="events", default=None
    )

    # Specific target users
    targeted_teachers = models.ManyToManyField(
        Teacher, blank=True, related_name="teacher_events"
    )
    targeted_parents = models.ManyToManyField(
        Parent, blank=True, related_name="parent_events"
    )
    targeted_classes = models.ManyToManyField(
        SchoolClass, blank=True, related_name="class_events"
    )

    # School term/year context
    current_school_year = models.CharField(max_length=20, blank=True, null=True)
    current_term = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ("term_1", "Term 1"),
            ("term_2", "Term 2"),
            ("term_3", "Term 3"),
        ],
    )

    # Event details
    location = models.CharField(max_length=255, blank=True, null=True)
    is_all_day = models.BooleanField(default=False)
    attachment = models.FileField(upload_to="event_attachments/", blank=True, null=True)
    requires_rsvp = models.BooleanField(default=False)
    rsvp_deadline = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_datetime"]
        indexes = [
            models.Index(fields=["start_datetime"]),
            models.Index(fields=["end_datetime"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["target_type"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_datetime.strftime('%Y-%m-%d')})"

    def clean(self):
        if self.end_datetime < self.start_datetime:
            raise ValidationError("End datetime must be after start datetime")

        if self.rsvp_deadline and self.rsvp_deadline > self.start_datetime:
            raise ValidationError("RSVP deadline must be before event start time")

    @classmethod
    def get_current_school_year(cls):
        today = timezone.now()
        event = (
            cls.objects.filter(
                current_school_year__isnull=False,
                start_datetime__lte=today,
                end_datetime__gte=today,
            )
            .order_by("-start_datetime")
            .first()
        )
        return event.current_school_year if event else None

    @classmethod
    def get_current_term(cls):
        today = timezone.now()
        event = (
            cls.objects.filter(
                current_term__isnull=False,
                start_datetime__lte=today,
                end_datetime__gte=today,
            )
            .order_by("-start_datetime")
            .first()
        )
        return event.current_term if event else None

    def get_target_users(self):
        """Get all users who should see this event"""
        if self.target_type == "all":
            return User.objects.filter(school=self.school)
        elif self.target_type == "teachers":
            return User.objects.filter(school=self.school, user_type=User.TEACHER)
        elif self.target_type == "parents":
            return User.objects.filter(school=self.school, user_type=User.PARENT)
        elif self.target_type == "specific":
            teachers = self.targeted_teachers.all().values_list("user", flat=True)
            parents = self.targeted_parents.all().values_list("user", flat=True)
            return User.objects.filter(
                models.Q(id__in=teachers) | models.Q(id__in=parents)
            )
        elif self.target_type == "classes":
            # Get teachers assigned to these classes
            teacher_users = User.objects.filter(
                teacher_profile__assigned_classes__in=self.targeted_classes.all()
            )
            # Get parents of students in these classes
            parent_users = User.objects.filter(
                parent_profile__children__school_class__in=self.targeted_classes.all()
            )
            return teacher_users.union(parent_users)
        return User.objects.none()


class EventRSVP(models.Model):
    RSVP_STATUS = [
        ("going", "Going"),
        ("not_going", "Not Going"),
        ("maybe", "Maybe"),
    ]
    event = models.ForeignKey(
        SchoolEvent, on_delete=models.CASCADE, related_name="rsvps"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_rsvps")
    status = models.CharField(max_length=20, choices=RSVP_STATUS, default="going")
    response_note = models.TextField(blank=True, null=True)
    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "user")
        verbose_name = "Event RSVP"
        verbose_name_plural = "Event RSVPs"

    def __str__(self):
        return f"{self.user} - {self.event}: {self.status}"
