from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.teacher import Teacher
from skul_data.students.models.student import Subject
from datetime import datetime, date


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

    def is_morning(self):
        """Check if this time slot is in the morning (before 12pm)"""
        return self.end_time.hour < 12

    def is_after_lunch(self):
        """Check if this time slot is after lunch (after 1pm)"""
        return self.start_time.hour >= 13

    def is_double_period(self):
        """Check if this is a double period slot"""
        duration = datetime.combine(date.today(), self.end_time) - datetime.combine(
            date.today(), self.start_time
        )
        return duration.total_seconds() >= 5400

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

    # In TimeSlot model, fix the save method and add proper ordering
    def save(self, *args, **kwargs):
        # Set day_order based on day_of_week
        self.day_order = self.DAY_ORDER.get(self.day_of_week, 1)

        # Auto-generate name if not provided and not a break
        if not self.name and not self.is_break:
            self.name = f"Period {self.order}"

        super().save(*args, **kwargs)

    # Also update the Meta ordering
    class Meta:
        unique_together = ("school", "start_time", "end_time", "day_of_week")
        ordering = ["day_order", "start_time", "order"]  # More precise ordering


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
    include_games = models.BooleanField(
        default=True, help_text="Include games period in the timetable"
    )
    games_duration = models.PositiveIntegerField(
        default=45, help_text="Duration of games period in minutes"
    )
    include_preps = models.BooleanField(
        default=False, help_text="Include preps period for boarding schools"
    )
    preps_duration = models.PositiveIntegerField(
        default=60, help_text="Duration of preps period in minutes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Timetable Structure for {self.school.name}"

    class Meta:
        ordering = ["-created_at"]

    def generate_time_slots(self):
        """Generate time slots with proper unique identifiers"""
        from datetime import datetime, time, timedelta

        # Clear existing time slots
        TimeSlot.objects.filter(school=self.school).delete()

        DAY_ORDER = {
            "MON": 1,
            "TUE": 2,
            "WED": 3,
            "THU": 4,
            "FRI": 5,
            "SAT": 6,
            "SUN": 7,
        }

        # Define unique time periods (these will repeat across days)
        period_templates = []
        current_time = datetime.combine(datetime.today(), self.default_start_time)
        end_time = datetime.combine(datetime.today(), self.default_end_time)
        period_number = 1

        # Morning periods (before 10:00)
        morning_end = datetime.combine(datetime.today(), time(10, 0))
        while current_time + timedelta(minutes=self.period_duration) <= morning_end:
            slot_end = current_time + timedelta(minutes=self.period_duration)
            period_templates.append(
                {
                    "name": f"Period {period_number}",
                    "start_time": current_time.time(),
                    "end_time": slot_end.time(),
                    "is_break": False,
                    "order": period_number,
                }
            )
            current_time = slot_end
            period_number += 1

        # Short break
        if current_time + timedelta(minutes=self.break_duration) <= end_time:
            break_end = current_time + timedelta(minutes=self.break_duration)
            period_templates.append(
                {
                    "name": "Short Break",
                    "start_time": current_time.time(),
                    "end_time": break_end.time(),
                    "is_break": True,
                    "break_name": "Short Break",
                    "order": period_number,
                }
            )
            current_time = break_end
            period_number += 1

        # Pre-lunch periods (10:30-12:30)
        lunch_start = datetime.combine(datetime.today(), time(12, 30))
        while current_time + timedelta(minutes=self.period_duration) <= lunch_start:
            slot_end = current_time + timedelta(minutes=self.period_duration)
            period_templates.append(
                {
                    "name": f"Period {period_number}",
                    "start_time": current_time.time(),
                    "end_time": slot_end.time(),
                    "is_break": False,
                    "order": period_number,
                }
            )
            current_time = slot_end
            period_number += 1

        # Lunch break
        if current_time + timedelta(minutes=self.lunch_duration) <= end_time:
            lunch_end = current_time + timedelta(minutes=self.lunch_duration)
            period_templates.append(
                {
                    "name": "Lunch Break",
                    "start_time": current_time.time(),
                    "end_time": lunch_end.time(),
                    "is_break": True,
                    "break_name": "Lunch",
                    "order": period_number,
                }
            )
            current_time = lunch_end
            period_number += 1

        # Afternoon periods
        afternoon_end = datetime.combine(datetime.today(), time(15, 0))
        while current_time + timedelta(minutes=self.period_duration) <= afternoon_end:
            slot_end = current_time + timedelta(minutes=self.period_duration)
            period_templates.append(
                {
                    "name": f"Period {period_number}",
                    "start_time": current_time.time(),
                    "end_time": slot_end.time(),
                    "is_break": False,
                    "order": period_number,
                }
            )
            current_time = slot_end
            period_number += 1

        # Games (if enabled)
        if (
            self.include_games
            and current_time + timedelta(minutes=self.games_duration) <= end_time
        ):
            games_end = current_time + timedelta(minutes=self.games_duration)
            period_templates.append(
                {
                    "name": "Games",
                    "start_time": current_time.time(),
                    "end_time": games_end.time(),
                    "is_break": True,
                    "break_name": "Games",
                    "order": period_number,
                }
            )
            current_time = games_end
            period_number += 1

        # Now create these templates for each day
        slots_created = 0
        for day in self.days_of_week:
            for template in period_templates:
                TimeSlot.objects.create(
                    school=self.school,
                    day_of_week=day,
                    day_order=DAY_ORDER.get(day, 1),
                    **template,
                )
                slots_created += 1

        return slots_created


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
    """Predefined constraints/rules for timetable generation"""

    CONSTRAINT_TYPE_CHOICES = [
        # Teacher-related constraints
        (
            "NO_TEACHER_CLASH",
            "No teacher double booking (same teacher in multiple classes at same time)",
        ),
        (
            "NO_TEACHER_SAME_SUBJECT_CLASH",
            "No same subject teaching at same time by same teacher",
        ),
        # Class-related constraints
        (
            "NO_CLASS_CLASH",
            "No class subject overlap (one subject per class per time slot)",
        ),
        # Subject-related constraints
        (
            "SCIENCE_DOUBLE_PERIOD",
            "Science subjects must have one double period per week (8-4-4 only)",
        ),
        (
            "NO_CORE_AFTER_LUNCH",
            "Core subjects (English, Kiswahili, Math) not after lunch",
        ),
        ("NO_DOUBLE_CORE", "No double lessons for core subjects"),
        ("MATH_NOT_AFTER_SCIENCE", "Mathematics must not follow science subjects"),
        ("MATH_MORNING_ONLY", "Mathematics must always be in the morning"),
        (
            "ENGLISH_KISWAHILI_SEPARATE",
            "English and Kiswahili must not follow each other",
        ),
        # Subject grouping constraints
        ("SUBJECT_GROUPING", "Group subjects that students don't take together"),
        # Structural constraints
        (
            "MANDATORY_BREAKS",
            "Include mandatory breaks (short break, long break, lunch)",
        ),
        ("INCLUDE_GAMES", "Include games period"),
        ("INCLUDE_PREPS", "Include preps period (boarding schools)"),
    ]

    CONSTRAINT_CATEGORIES = [
        ("TEACHER", "Teacher Constraints"),
        ("SUBJECT", "Subject Constraints"),
        ("STRUCTURE", "Structural Constraints"),
    ]

    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="timetable_constraints"
    )
    constraint_type = models.CharField(
        max_length=50,
        choices=CONSTRAINT_TYPE_CHOICES,
        help_text="Select from predefined constraint types",
    )
    category = models.CharField(
        max_length=10, choices=CONSTRAINT_CATEGORIES, blank=True, null=True
    )
    is_hard_constraint = models.BooleanField(
        default=True,
        help_text="Hard constraints cannot be violated. Soft constraints are preferred but not required",
    )
    parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional parameters for the constraint (e.g., subject groups)",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Explanation of how this constraint will be applied",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "constraint_type"]
        verbose_name = "Timetable Constraint"
        verbose_name_plural = "Timetable Constraints"

    def __str__(self):
        return f"{self.get_constraint_type_display()} ({'Hard' if self.is_hard_constraint else 'Soft'})"

    def save(self, *args, **kwargs):
        # Automatically set category based on constraint type
        if self.constraint_type in [
            "NO_TEACHER_CLASH",
            "NO_TEACHER_SAME_SUBJECT_CLASH",
        ]:
            self.category = "TEACHER"
        elif self.constraint_type in [
            "SCIENCE_DOUBLE_PERIOD",
            "NO_CORE_AFTER_LUNCH",
            "NO_DOUBLE_CORE",
            "MATH_NOT_AFTER_SCIENCE",
            "MATH_MORNING_ONLY",
            "ENGLISH_KISWAHILI_SEPARATE",
            "SUBJECT_GROUPING",
        ]:
            self.category = "SUBJECT"
        else:
            self.category = "STRUCTURE"

        # Set default descriptions for each constraint type
        if not self.description:
            self.description = self.get_default_description()

        super().save(*args, **kwargs)

    def get_default_description(self):
        descriptions = {
            "NO_TEACHER_CLASH": "Ensures a teacher is not scheduled in multiple classes at the same time",
            "NO_TEACHER_SAME_SUBJECT_CLASH": "Prevents same teacher teaching same subject in different classes simultaneously",
            "NO_CLASS_CLASH": "Ensures only one subject is scheduled per class at any time",
            "SCIENCE_DOUBLE_PERIOD": "Science subjects must have one double period per week (for 8-4-4 curriculum)",
            "NO_CORE_AFTER_LUNCH": "Core subjects (English, Kiswahili, Math) cannot be scheduled after lunch",
            "NO_DOUBLE_CORE": "Core subjects cannot have double periods",
            "MATH_NOT_AFTER_SCIENCE": "Mathematics lessons cannot be scheduled immediately after science subjects",
            "MATH_MORNING_ONLY": "Mathematics must be scheduled in morning sessions only",
            "ENGLISH_KISWAHILI_SEPARATE": "English and Kiswahili lessons cannot be scheduled consecutively",
            "SUBJECT_GROUPING": "Groups subjects that students don't take together (e.g., Business, Computer, Agriculture)",
            "MANDATORY_BREAKS": "Ensures timetable includes short break, long break and lunch break",
            "INCLUDE_GAMES": "Includes games period in the timetable",
            "INCLUDE_PREPS": "Includes preps period for boarding schools",
        }
        return descriptions.get(self.constraint_type, "")


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
