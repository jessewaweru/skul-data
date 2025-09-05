from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class AcademicRecord(models.Model):
    """Tracks a student's academic performance in a subject for a term"""

    GRADE_CHOICES = [
        ("A", "Excellent (A)"),
        ("B", "Good (B)"),
        ("C", "Average (C)"),
        ("D", "Below Average (D)"),
        ("E", "Poor (E)"),
        ("F", "Fail (F)"),
    ]

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="academic_records"
    )
    subject = models.ForeignKey(
        "students.Subject",
        on_delete=models.PROTECT,
        related_name="student_records",
    )
    teacher = models.ForeignKey(
        "users.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taught_records",
    )
    term = models.CharField(max_length=40)  # e.g., "Term 1", "Mid-Term"
    school_year = models.CharField(
        max_length=20,
    )  # e.g., "2023-2024"
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES)
    subject_comments = models.TextField(
        blank=True,
        null=True,
        help_text="Teacher's comments about performance in this specific subject",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(
        default=False, help_text="Whether this record is visible to parents"
    )

    class Meta:
        unique_together = ("student", "subject", "term", "school_year")
        ordering = ["term", "subject__name"]
        verbose_name = "Academic Record"
        verbose_name_plural = "Academic Records"

    def __str__(self):
        return f"{self.student} - {self.subject.name if self.subject else 'No Subject'} ({self.term} {self.school_year})"

    def save(self, *args, **kwargs):
        # Calculate grade when the record is new or the score has changed
        if not self.pk or (
            self.pk
            and hasattr(self, "_loaded_score")
            and self.score != self._loaded_score
        ):
            self.grade = self.calculate_grade()

        # Save the record
        result = super().save(*args, **kwargs)

        # Store the current score to compare on next save
        self._loaded_score = self.score

        return result

    @classmethod
    def from_db(cls, db, field_names, values):
        # This method is called when the model is loaded from the database
        instance = super().from_db(db, field_names, values)

        # Store the original score value for comparison in save()
        instance._loaded_score = instance.score

        return instance

    def calculate_grade(self):
        """Calculate grade based on score"""
        if self.score >= 80:
            return "A"
        elif self.score >= 70:
            return "B"
        elif self.score >= 60:
            return "C"
        elif self.score >= 50:
            return "D"
        elif self.score >= 30:
            return "E"
        else:
            return "F"

    @property
    def performance_assessment(self):
        """Get a textual assessment of performance"""
        assessments = {
            "A": "Excellent performance",
            "B": "Good performance",
            "C": "Satisfactory performance",
            "D": "Needs improvement",
            "E": "Poor performance",
            "F": "Failed - requires remediation",
        }
        return assessments.get(self.grade, "No assessment available")


# students/models.py
class TeacherComment(models.Model):
    """Formal teacher comments about a student's overall performance for a term"""

    COMMENT_TYPE_CHOICES = [
        ("GENERAL", "General Comment"),
        ("STRENGTH", "Key Strength"),
        ("IMPROVE", "Area for Improvement"),
        ("RECOMMENDATION", "Recommendation"),
    ]

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="teacher_comments"
    )
    teacher = models.ForeignKey(
        "users.Teacher", on_delete=models.CASCADE, related_name="student_comments"
    )
    term = models.CharField(max_length=20)
    school_year = models.CharField(max_length=20)
    comment_type = models.CharField(
        max_length=20, choices=COMMENT_TYPE_CHOICES, default="GENERAL"
    )
    content = models.TextField(
        help_text="Detailed comments about the student's performance"
    )
    is_approved = models.BooleanField(
        default=False,
        help_text="Whether the comment has been approved by administration",
    )
    approved_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_comments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "teacher", "term", "school_year", "comment_type")
        ordering = ["-school_year", "term", "student"]
        verbose_name = "Teacher Comment"
        verbose_name_plural = "Teacher Comments"

    def __str__(self):
        return f"{self.teacher} on {self.student} ({self.term} {self.school_year})"

    def approve(self, user):
        """Mark comment as approved by administrator"""
        self.is_approved = True
        self.approved_by = user
        self.save()
