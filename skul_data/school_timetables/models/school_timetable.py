from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.teacher import Teacher
from skul_data.students.models.student import Subject


class TimeSlot(models.Model):
    """Represents a time slot in the school timetable"""

    DAYS_OF_WEEK = [
        ("MON", "Monday"),
        ("TUE", "Tuesday"),
        ("WED", "Wednesday"),
        ("THU", "Thursday"),
        ("FRI", "Friday"),
        ("SAT", "Saturday"),
        ("SUN", "Sunday"),
    ]

    # Map days to their order for sorting
    DAY_ORDER = {
        "MON": 1,
        "TUE": 2,
        "WED": 3,
        "THU": 4,
        "FRI": 5,
        "SAT": 6,
        "SUN": 7,
    }

    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="time_slots"
    )
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    day_of_week = models.CharField(max_length=3, choices=DAYS_OF_WEEK)
    day_order = models.PositiveIntegerField(default=1)  # Add this field
    is_break = models.BooleanField(default=False)
    break_name = models.CharField(max_length=50, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("school", "start_time", "end_time", "day_of_week")
        ordering = ["day_order", "order"]  # Changed from day_of_week to day_order

    def save(self, *args, **kwargs):
        # Automatically set day_order based on day_of_week
        if not self.day_order or self.day_order == 1:
            self.day_order = self.DAY_ORDER.get(self.day_of_week, 1)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.is_break:
            return f"{self.break_name} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"
        return f"{self.name} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"

    def clean(self):
        if self.is_break and not self.break_name:
            raise ValidationError("Break name is required for break time slots")
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")


class TimetableStructure(models.Model):
    """Defines the structure of timetables for a school"""

    CURRICULUM_CHOICES = [
        ("CBC", "Competency Based Curriculum (CBC)"),
        ("8-4-4", "8-4-4 System"),
    ]

    school = models.OneToOneField(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="school_timetable_structure",
    )
    curriculum = models.CharField(
        max_length=10, choices=CURRICULUM_CHOICES, default="CBC"
    )
    days_of_week = ArrayField(
        models.CharField(max_length=3, choices=TimeSlot.DAYS_OF_WEEK),
        default=list,
        help_text="Days of the week when school is in session",
    )
    default_start_time = models.TimeField(default="08:00")
    default_end_time = models.TimeField(default="16:00")
    period_duration = models.PositiveIntegerField(
        default=40, help_text="Duration of each period in minutes"
    )
    break_duration = models.PositiveIntegerField(
        default=30, help_text="Duration of break in minutes"
    )
    lunch_duration = models.PositiveIntegerField(
        default=60, help_text="Duration of lunch break in minutes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Timetable Structure for {self.school.name}"

    class Meta:
        ordering = ["-created_at"]

    def generate_time_slots(self):
        """Generate standard time slots based on the structure"""
        from datetime import datetime, time, timedelta

        TimeSlot.objects.filter(school=self.school).delete()

        # Calculate periods
        period_duration = timedelta(minutes=self.period_duration)
        break_duration = timedelta(minutes=self.break_duration)
        lunch_duration = timedelta(minutes=self.lunch_duration)

        for day in self.days_of_week:
            current_time = datetime.combine(datetime.today(), self.default_start_time)
            end_time = datetime.combine(datetime.today(), self.default_end_time)
            period_number = 1

            # Morning session
            while current_time + period_duration <= datetime.combine(
                datetime.today(), time(12, 0)
            ):
                TimeSlot.objects.create(
                    school=self.school,
                    name=f"Period {period_number}",
                    start_time=current_time.time(),
                    end_time=(current_time + period_duration).time(),
                    day_of_week=day,
                    order=period_number,
                )
                current_time += period_duration
                period_number += 1

            # Morning break
            TimeSlot.objects.create(
                school=self.school,
                name="Morning Break",
                start_time=current_time.time(),
                end_time=(current_time + break_duration).time(),
                day_of_week=day,
                is_break=True,
                break_name="Morning Break",
                order=period_number,
            )
            current_time += break_duration
            period_number += 1

            # Pre-lunch session
            while current_time + period_duration <= datetime.combine(
                datetime.today(), time(13, 0)
            ):
                TimeSlot.objects.create(
                    school=self.school,
                    name=f"Period {period_number}",
                    start_time=current_time.time(),
                    end_time=(current_time + period_duration).time(),
                    day_of_week=day,
                    order=period_number,
                )
                current_time += period_duration
                period_number += 1

            # Lunch break
            TimeSlot.objects.create(
                school=self.school,
                name="Lunch Break",
                start_time=current_time.time(),
                end_time=(current_time + lunch_duration).time(),
                day_of_week=day,
                is_break=True,
                break_name="Lunch",
                order=period_number,
            )
            current_time += lunch_duration
            period_number += 1

            # Afternoon session
            while current_time + period_duration <= end_time:
                TimeSlot.objects.create(
                    school=self.school,
                    name=f"Period {period_number}",
                    start_time=current_time.time(),
                    end_time=(current_time + period_duration).time(),
                    day_of_week=day,
                    order=period_number,
                )
                current_time += period_duration
                period_number += 1


class Timetable(models.Model):
    """Represents a timetable for a specific class"""

    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="school_timetables"
    )
    academic_year = models.CharField(max_length=20)
    term = models.PositiveIntegerField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("school_class", "academic_year", "term")
        ordering = ["academic_year", "term", "school_class"]

    def __str__(self):
        return (
            f"Timetable for {self.school_class} ({self.academic_year} Term {self.term})"
        )

    def clean(self):
        # Ensure only one active timetable per class
        if self.is_active:
            active_timetables = Timetable.objects.filter(
                school_class=self.school_class, is_active=True
            ).exclude(pk=self.pk)
            if active_timetables.exists():
                raise ValidationError(
                    "There can only be one active timetable per class"
                )


class Lesson(models.Model):
    """Represents a lesson in the timetable"""

    timetable = models.ForeignKey(
        Timetable, on_delete=models.CASCADE, related_name="lessons"
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    is_double_period = models.BooleanField(default=False)
    room = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("timetable", "time_slot")
        ordering = ["time_slot__day_of_week", "time_slot__order"]

    def __str__(self):
        return f"{self.subject.name} with {self.teacher} at {self.time_slot}"


class TimetableConstraint(models.Model):
    """Constraints/rules for timetable generation"""

    CONSTRAINT_TYPE_CHOICES = [
        ("NO_TEACHER_CLASH", "No teacher double booking"),
        ("NO_CLASS_CLASH", "No class subject overlap"),
        ("SUBJECT_PAIRING", "Subject pairing"),
        ("SCIENCE_DOUBLE", "Science double period"),
        ("NO_AFTERNOON_SCIENCE", "No science in afternoon"),
        ("MAX_PERIODS_PER_DAY", "Maximum periods per day"),
        ("MIN_PERIODS_BETWEEN", "Minimum periods between subjects"),
        ("TEACHER_AVAILABILITY", "Teacher availability"),
        ("ROOM_AVAILABILITY", "Room availability"),
        ("SUBJECT_PREFERENCE", "Subject time preference"),
    ]

    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="timetable_constraints"
    )
    constraint_type = models.CharField(max_length=50, choices=CONSTRAINT_TYPE_CHOICES)
    is_hard_constraint = models.BooleanField(default=True)
    parameters = models.JSONField(default=dict)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["is_hard_constraint", "constraint_type"]

    def __str__(self):
        return f"{self.get_constraint_type_display()} ({'Hard' if self.is_hard_constraint else 'Soft'})"

    def clean(self):
        if self.constraint_type == "SUBJECT_PAIRING" and not self.parameters.get(
            "subjects"
        ):
            raise ValidationError("Subject pairing requires a list of subject IDs")
        if self.constraint_type == "MAX_PERIODS_PER_DAY" and not self.parameters.get(
            "max_periods"
        ):
            raise ValidationError("Max periods per day requires a maximum number")
        if self.constraint_type == "MIN_PERIODS_BETWEEN" and not all(
            key in self.parameters for key in ["subject_id", "min_periods"]
        ):
            raise ValidationError(
                "Min periods between requires subject_id and min_periods"
            )


class SubjectGroup(models.Model):
    """Groups of subjects that can be paired together in timetables"""

    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="subject_groups"
    )
    name = models.CharField(max_length=100)
    subjects = models.ManyToManyField(Subject, related_name="subject_groups")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("school", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.school.name})"


class TeacherAvailability(models.Model):
    """Teacher availability for timetable scheduling"""

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="availabilities"
    )
    day_of_week = models.CharField(max_length=3, choices=TimeSlot.DAYS_OF_WEEK)
    is_available = models.BooleanField(default=True)
    available_from = models.TimeField(blank=True, null=True)
    available_to = models.TimeField(blank=True, null=True)
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("teacher", "day_of_week")
        ordering = ["teacher", "day_of_week"]
        verbose_name_plural = "Teacher availabilities"

    def __str__(self):
        return f"{self.teacher} - {self.get_day_of_week_display()} ({'Available' if self.is_available else 'Unavailable'})"

    def clean(self):
        if self.is_available and (self.available_from or self.available_to):
            if not (self.available_from and self.available_to):
                raise ValidationError(
                    "Both available_from and available_to must be set when specifying availability times"
                )
            if self.available_from >= self.available_to:
                raise ValidationError(
                    "Available to time must be after available from time"
                )
