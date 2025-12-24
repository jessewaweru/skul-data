from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from skul_data.schools.models.school import School
from skul_data.students.models.student import Student
from skul_data.students.models.student import Subject
from skul_data.users.models.teacher import Teacher


class KCSEResult(models.Model):
    GRADE_CHOICES = [
        ("A", "A (80-100)"),
        ("A-", "A- (75-79)"),
        ("B+", "B+ (70-74)"),
        ("B", "B (65-69)"),
        ("B-", "B- (60-64)"),
        ("C+", "C+ (55-59)"),
        ("C", "C (50-54)"),
        ("C-", "C- (45-49)"),
        ("D+", "D+ (40-44)"),
        ("D", "D (35-39)"),
        ("D-", "D- (30-34)"),
        ("E", "E (0-29)"),
    ]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="kcse_results"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="kcse_results"
    )
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(1989), MaxValueValidator(timezone.now().year)]
    )
    index_number = models.CharField(max_length=20)
    mean_grade = models.CharField(max_length=2, choices=GRADE_CHOICES)
    mean_points = models.DecimalField(max_digits=5, decimal_places=2)
    division = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("school", "student", "year")
        ordering = ["-year", "student__last_name"]
        verbose_name = "KCSE Result"
        verbose_name_plural = "KCSE Results"

    def __str__(self):
        return f"{self.student.full_name} - {self.year} ({self.mean_grade})"


class KCSESubjectResult(models.Model):
    kcse_result = models.ForeignKey(
        KCSEResult, on_delete=models.CASCADE, related_name="subject_results"
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    subject_code = models.CharField(max_length=10)
    grade = models.CharField(max_length=2, choices=KCSEResult.GRADE_CHOICES)
    points = models.PositiveSmallIntegerField()
    subject_teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True
    )
    mean_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    mean_grade = models.CharField(
        max_length=2, choices=KCSEResult.GRADE_CHOICES, null=True, blank=True
    )

    class Meta:
        unique_together = ("kcse_result", "subject")
        verbose_name = "KCSE Subject Result"
        verbose_name_plural = "KCSE Subject Results"

    def __str__(self):
        return (
            f"{self.kcse_result.student.full_name} - {self.subject.name} ({self.grade})"
        )


class KCSESchoolPerformance(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="kcse_performances"
    )
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(1989), MaxValueValidator(timezone.now().year)]
    )
    mean_grade = models.CharField(max_length=2, choices=KCSEResult.GRADE_CHOICES)
    mean_points = models.DecimalField(max_digits=5, decimal_places=2)
    total_students = models.PositiveIntegerField()
    university_qualified = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("school", "year")
        ordering = ["-year"]
        verbose_name = "KCSE School Performance"
        verbose_name_plural = "KCSE School Performances"

    def __str__(self):
        return f"{self.school.name} - {self.year} ({self.mean_grade})"


class KCSESubjectPerformance(models.Model):
    school_performance = models.ForeignKey(
        KCSESchoolPerformance,
        on_delete=models.CASCADE,
        related_name="subject_performances",
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    subject_code = models.CharField(max_length=10)
    mean_score = models.DecimalField(max_digits=5, decimal_places=2)
    mean_grade = models.CharField(max_length=2, choices=KCSEResult.GRADE_CHOICES)
    total_students = models.PositiveIntegerField()
    entered = models.PositiveIntegerField()
    passed = models.PositiveIntegerField()
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(1989), MaxValueValidator(timezone.now().year)],
        default=timezone.now().year,
    )
    subject_teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        unique_together = ("school_performance", "subject")
        verbose_name = "KCSE Subject Performance"
        verbose_name_plural = "KCSE Subject Performances"

    def __str__(self):
        return f"{self.school_performance.school.name} - {self.subject.name} ({self.mean_grade})"
