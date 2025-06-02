from django.db import models
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory

User = get_user_model()


# class SchoolEvent(models.Model):
#     EVENT_TYPES = [
#         ("general", "General"),
#         ("meeting", "Meeting"),
#         ("exam", "Exam"),
#         ("holiday", "Holiday"),
#         ("announcement", "Announcement"),
#         ("parent_event", "Parent Event"),
#         ("staff_event", "Staff Event"),
#     ]

#     EVENT_TARGETS = [
#         ("all", "Everyone"),
#         ("teachers", "Teachers"),
#         ("parents", "Parents"),
#         ("specific", "Specific Users"),
#         ("classes", "Specific Classes"),
#     ]

#     title = models.CharField(max_length=255)
#     description = models.TextField(blank=True, null=True)
#     start_datetime = models.DateTimeField()
#     end_datetime = models.DateTimeField()
#     event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default="general")
#     target_type = models.CharField(max_length=20, choices=EVENT_TARGETS, default="all")

#     # Who created the event (usually the school admin)
#     created_by = models.ForeignKey(
#         User, on_delete=models.CASCADE, related_name="created_events"
#     )
#     school = models.ForeignKey(
#         "schools.School", on_delete=models.CASCADE, related_name="events", default=None
#     )
#     # current_term = models.CharField(
#     #     max_length=20,
#     #     choices=[("term_1", "Term 1"), ("term_2", "Term 2"), ("term_3", "Term 3")],
#     #     null=True,
#     #     blank=True,
#     # )
#     # current_school_year = models.CharField(max_length=20, null=True, blank=True)
#     # Specific target users
#     targeted_teachers = models.ManyToManyField(
#         Teacher, blank=True, related_name="teacher_events"
#     )
#     targeted_parents = models.ManyToManyField(
#         Parent, blank=True, related_name="parent_events"
#     )
#     targeted_classes = models.ManyToManyField(
#         SchoolClass, blank=True, related_name="class_events"
#     )

#     # Event details
#     location = models.CharField(max_length=255, blank=True, null=True)
#     is_all_day = models.BooleanField(default=False)
#     attachment = models.FileField(upload_to="event_attachments/", blank=True, null=True)
#     requires_rsvp = models.BooleanField(default=False)
#     rsvp_deadline = models.DateTimeField(blank=True, null=True)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ["-start_datetime"]
#         indexes = [
#             models.Index(fields=["start_datetime"]),
#             models.Index(fields=["end_datetime"]),
#             models.Index(fields=["event_type"]),
#             models.Index(fields=["target_type"]),
#         ]

#     def __str__(self):
#         return f"{self.title} ({self.start_datetime.strftime('%Y-%m-%d')})"

#     def clean(self):
#         if self.end_datetime < self.start_datetime:
#             raise ValidationError("End datetime must be after start datetime")

#         if self.rsvp_deadline and self.rsvp_deadline > self.start_datetime:
#             raise ValidationError("RSVP deadline must be before event start time")

#     @classmethod
#     def get_current_school_year(cls):
#         today = timezone.now()
#         event = (
#             cls.objects.filter(
#                 current_school_year__isnull=False,
#                 start_datetime__lte=today,
#                 end_datetime__gte=today,
#             )
#             .order_by("-start_datetime")
#             .first()
#         )
#         return event.current_school_year if event else None

#     def get_target_users(self):
#         """
#         Returns the users who are targets for this event based on target_type.
#         """
#         if self.target_type == "all":
#             # Get all users associated with this school through Teacher and Parent profiles
#             teachers = Teacher.objects.filter(school=self.school).values_list(
#                 "user", flat=True
#             )
#             parents = Parent.objects.filter(school=self.school).values_list(
#                 "user", flat=True
#             )
#             return User.objects.filter(Q(id__in=teachers) | Q(id__in=parents))

#         elif self.target_type == "teachers":
#             teacher_users = Teacher.objects.filter(school=self.school).values_list(
#                 "user", flat=True
#             )
#             return User.objects.filter(id__in=teacher_users)

#         elif self.target_type == "parents":
#             parent_users = Parent.objects.filter(school=self.school).values_list(
#                 "user", flat=True
#             )
#             return User.objects.filter(id__in=parent_users)

#         elif self.target_type == "specific":
#             teachers = self.targeted_teachers.values_list("user", flat=True)
#             parents = self.targeted_parents.values_list("user", flat=True)
#             return User.objects.filter(Q(id__in=teachers) | Q(id__in=parents))

#         elif self.target_type == "classes":
#             # Get teachers assigned to targeted classes
#             teachers = Teacher.objects.filter(
#                 assigned_classes__in=self.targeted_classes.all(), school=self.school
#             ).values_list("user", flat=True)

#             # Get parents with children in targeted classes - checking both parent FK and guardians
#             parents = (
#                 Parent.objects.filter(
#                     Q(primary_students__student_class__in=self.targeted_classes.all())
#                     | Q(
#                         guardian_students__student_class__in=self.targeted_classes.all()
#                     ),
#                     school=self.school,
#                 )
#                 .distinct()
#                 .values_list("user", flat=True)
#             )

#             return User.objects.filter(Q(id__in=teachers) | Q(id__in=parents))


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

    # Who created the event (usually the school admin)
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

    def get_target_users(self):
        """
        Returns the users who are targets for this event based on target_type.
        """
        if self.target_type == "all":
            # Get all users associated with this school through Teacher and Parent profiles
            teachers = Teacher.objects.filter(school=self.school).values_list(
                "user", flat=True
            )
            parents = Parent.objects.filter(school=self.school).values_list(
                "user", flat=True
            )
            return User.objects.filter(Q(id__in=teachers) | Q(id__in=parents))

        elif self.target_type == "teachers":
            teacher_users = Teacher.objects.filter(school=self.school).values_list(
                "user", flat=True
            )
            return User.objects.filter(id__in=teacher_users)

        elif self.target_type == "parents":
            parent_users = Parent.objects.filter(school=self.school).values_list(
                "user", flat=True
            )
            return User.objects.filter(id__in=parent_users)

        elif self.target_type == "specific":
            teachers = self.targeted_teachers.values_list("user", flat=True)
            parents = self.targeted_parents.values_list("user", flat=True)
            return User.objects.filter(Q(id__in=teachers) | Q(id__in=parents))

        elif self.target_type == "classes":
            # Get teachers assigned to targeted classes
            teachers = Teacher.objects.filter(
                assigned_classes__in=self.targeted_classes.all(), school=self.school
            ).values_list("user", flat=True)

            # Get parents with children in targeted classes - checking both parent FK and guardians
            parents = (
                Parent.objects.filter(
                    Q(primary_students__student_class__in=self.targeted_classes.all())
                    | Q(
                        guardian_students__student_class__in=self.targeted_classes.all()
                    ),
                    school=self.school,
                )
                .distinct()
                .values_list("user", flat=True)
            )

            return User.objects.filter(Q(id__in=teachers) | Q(id__in=parents))

    # ===================
    # ACTION LOGGING METHODS
    # ===================

    def save_related_logs(self, user, action):
        """
        Helper method to log changes to many-to-many relationships
        Args:
            user: User who made the changes
            action: Description of the action being logged
        """
        log_action(
            user=user,
            action=f"{action} related objects for event {self.id}",
            category=ActionCategory.UPDATE,
            obj=self,
            metadata={
                "targeted_teachers": list(
                    self.targeted_teachers.values_list("id", flat=True)
                ),
                "targeted_parents": list(
                    self.targeted_parents.values_list("id", flat=True)
                ),
                "targeted_classes": list(
                    self.targeted_classes.values_list("id", flat=True)
                ),
            },
        )

    def targeted_teachers_set(self, teachers, user=None):
        """
        Custom setter for targeted_teachers that logs the changes
        Args:
            teachers: List of Teacher instances to set
            user: Optional user who made the change (falls back to _current_user)
        """
        self.targeted_teachers.set(teachers)
        self.save_related_logs(
            user or getattr(self, "_current_user", None), "Updated teachers for"
        )

    def targeted_parents_set(self, parents, user=None):
        """
        Custom setter for targeted_parents that logs the changes
        Args:
            parents: List of Parent instances to set
            user: Optional user who made the change (falls back to _current_user)
        """
        self.targeted_parents.set(parents)
        self.save_related_logs(
            user or getattr(self, "_current_user", None), "Updated parents for"
        )

    def targeted_classes_set(self, classes, user=None):
        """
        Custom setter for targeted_classes that logs the changes
        Args:
            classes: List of SchoolClass instances to set
            user: Optional user who made the change (falls back to _current_user)
        """
        self.targeted_classes.set(classes)
        self.save_related_logs(
            user or getattr(self, "_current_user", None), "Updated classes for"
        )

    def log_attachment_upload(self, user=None):
        """
        Logs when an attachment is uploaded to an event
        Args:
            user: Optional user who uploaded the file (falls back to _current_user)
        """
        if not self.attachment:
            return

        log_action(
            user=user or getattr(self, "_current_user", None),
            action=f"Uploaded attachment to event {self.id}",
            category=ActionCategory.UPLOAD,
            obj=self,
            metadata={
                "filename": self.attachment.name,
                "size": self.attachment.size,
                "event_title": self.title,
            },
        )

    # def save(self, *args, **kwargs):
    #     """
    #     Override save to handle attachment logging
    #     """
    #     attachment_changed = False
    #     if self.pk:
    #         old = SchoolEvent.objects.get(pk=self.pk)
    #         attachment_changed = old.attachment != self.attachment

    #     super().save(*args, **kwargs)

    #     if attachment_changed and self.attachment:
    #         self.log_attachment_upload()

    def save(self, *args, **kwargs):
        """
        Override save to handle attachment logging
        """
        attachment_changed = False
        if self.pk:
            old = SchoolEvent.objects.get(pk=self.pk)
            attachment_changed = old.attachment != self.attachment

        # Get the user from kwargs if available (passed from admin or views)
        user = kwargs.pop("user", None)

        super().save(*args, **kwargs)

        if attachment_changed and self.attachment:
            self.log_attachment_upload(user=user)


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
