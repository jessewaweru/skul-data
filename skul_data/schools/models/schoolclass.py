from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolstream import SchoolStream


class SchoolClass(models.Model):
    GRADE_LEVEL_CHOICES = [
        ("Kindergarten", "Kindergarten"),
        ("Pre-primary 1", "Pre-primary 1"),
        ("Pre-primary 2", "Pre-primary 2"),
        ("Grade 1", "Grade 1"),
        ("Grade 2", "Grade 2"),
        ("Grade 3", "Grade 3"),
        ("Grade 4", "Grade 4"),
        ("Grade 5", "Grade 5"),
        ("Grade 6", "Grade 6"),
        ("Grade 7", "Grade 7"),
        ("Grade 8", "Grade 8"),
        ("Grade 9", "Grade 9"),
        ("Grade 10", "Grade 10"),
        ("Grade 11", "Grade 11"),
        ("Grade 12", "Grade 12"),
        ("Form 1", "Form 1"),
        ("Form 2", "Form 2"),
        ("Form 3", "Form 3"),
        ("Form 4", "Form 4"),
    ]

    LEVEL_CHOICES = [
        ("PRIMARY", "Primary"),
        ("SECONDARY", "Secondary"),
    ]

    name = models.CharField(max_length=100)
    grade_level = models.CharField(max_length=20, choices=GRADE_LEVEL_CHOICES)
    stream = models.ForeignKey(
        SchoolStream,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classes",
    )
    level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, null=True, blank=True
    )
    class_teacher = models.ForeignKey(
        "users.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classes_taught",
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="classes")
    students = models.ManyToManyField(
        "students.Student", related_name="classes", blank=True
    )
    subjects = models.ManyToManyField(
        "students.Subject", related_name="classes", blank=True
    )
    academic_year = models.CharField(max_length=20, null=True, blank=True)
    room_number = models.CharField(max_length=10, blank=True, null=True)
    capacity = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(10), MaxValueValidator(50)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "school", "academic_year")
        ordering = ["level", "grade_level", "name"]
        verbose_name_plural = "Classes"

    def __str__(self):
        return f"{self.name} ({self.academic_year})"

    @property
    def student_count(self):
        return self.students.count()

    @property
    def average_performance(self):
        from skul_data.reports.models.academic_record import AcademicRecord

        avg = AcademicRecord.objects.filter(student__in=self.students.all()).aggregate(
            models.Avg("score")
        )["score__avg"]
        return round(avg, 2) if avg else None

    def promote_class(self, new_academic_year):
        """Promote class to next academic year"""
        if not self.is_active:
            raise ValueError("Cannot promote inactive class")

        # Create new class with same properties but new academic year
        new_class = SchoolClass.objects.create(
            name=self.name,
            grade_level=self.grade_level,
            stream=self.stream,
            level=self.level,
            school=self.school,
            academic_year=new_academic_year,
            room_number=self.room_number,
            capacity=self.capacity,
        )

        # Copy subjects to new class
        new_class.subjects.set(self.subjects.all())

        return new_class

    def clean(self):
        if (
            SchoolClass.objects.filter(
                name=self.name, school=self.school, academic_year=self.academic_year
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                "A class with this name already exists for this particular school and academic year."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ClassTimetable(models.Model):
    """Timetable for a specific class"""

    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="timetables"
    )
    file = models.FileField(upload_to="timetables/%Y/%m/%d/")
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def __str__(self):
        return f"Timetable for {self.school_class}"


class ClassDocument(models.Model):
    """Documents related to a specific class"""

    DOCUMENT_TYPES = [
        ("ASSIGNMENT", "Assignment"),
        ("NOTES", "Teacher Notes"),
        ("SYLLABUS", "Syllabus"),
        ("OTHER", "Other"),
    ]

    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to="class_documents/%Y/%m/%d/")
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="class_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.title} ({self.get_document_type_display()}) for {self.school_class}"
        )


class ClassAttendance(models.Model):
    """Attendance records for a specific class"""

    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField()
    present_students = models.ManyToManyField(
        "students.Student", related_name="attendances"
    )
    taken_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="taken_attendances",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_students = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("school_class", "date")
        ordering = ["-date"]

    def save(self, *args, **kwargs):
        """Automatically capture student count when creating new attendance"""
        if not self.pk:  # Only on initial creation
            self.total_students = self.school_class.students.count()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attendance for {self.school_class} on {self.date}"

    @property
    def attendance_rate(self):
        total = self.school_class.students.count()
        present = self.present_students.count()
        return round((present / total) * 100, 2) if total > 0 else 0
