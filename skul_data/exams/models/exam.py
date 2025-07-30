from django.db import models
from django.forms import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum, Avg, Max, Min, Count
from decimal import Decimal
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Student, Subject
from skul_data.users.models.teacher import Teacher


class ExamType(models.Model):
    """Predefined exam types (Opener, Midterm, Endterm, Assessment) and custom types"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class GradingSystem(models.Model):
    """Grading systems that schools can choose from or create"""

    name = models.CharField(max_length=100)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="grading_systems"
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "school")
        ordering = ["-is_default", "name"]

    def __str__(self):
        return f"{self.name} ({self.school.name})"

    def clean(self):
        if self.is_default:
            existing_default = (
                GradingSystem.objects.filter(school=self.school, is_default=True)
                .exclude(pk=self.pk)
                .exists()
            )
            if existing_default:
                raise ValidationError(
                    "Only one default grading system allowed per school"
                )
        super().clean()


class GradeRange(models.Model):
    """Grade ranges for a grading system"""

    grading_system = models.ForeignKey(
        GradingSystem, on_delete=models.CASCADE, related_name="grade_ranges"
    )
    min_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    grade = models.CharField(max_length=10)
    remark = models.CharField(max_length=100, blank=True, null=True)
    points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["-min_score"]
        unique_together = ("grading_system", "min_score", "max_score")

    def __str__(self):
        return f"{self.grade} ({self.min_score}-{self.max_score})"

    def clean(self):
        if self.min_score >= self.max_score:
            raise ValidationError("Min score must be less than max score")
        super().clean()


class Exam(models.Model):
    """An exam instance (e.g., Term 1 Opener Exam 2023)"""

    name = models.CharField(max_length=200)
    exam_type = models.ForeignKey(
        ExamType, on_delete=models.PROTECT, related_name="exams"
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="exams")
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="exams"
    )
    term = models.CharField(max_length=20)  # e.g., "Term 1", "Term 2", "Term 3"
    academic_year = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    grading_system = models.ForeignKey(
        GradingSystem, on_delete=models.PROTECT, related_name="exams"
    )
    is_published = models.BooleanField(default=False)
    include_in_term_report = models.BooleanField(default=True)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "school_class", "term", "academic_year")
        ordering = ["-academic_year", "term", "start_date"]

    def __str__(self):
        return (
            f"{self.name} - {self.school_class.name} ({self.term} {self.academic_year})"
        )

    @property
    def status(self):
        today = timezone.now().date()
        if today < self.start_date:
            return "Upcoming"
        elif today >= self.start_date and today <= self.end_date:
            return "Ongoing"
        else:
            return "Completed"


class ExamSubject(models.Model):
    """Subjects included in an exam"""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="subjects")
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="exam_subjects"
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_subjects",
    )
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        default=100,
    )
    pass_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        blank=True,
        null=True,
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        default=100,
        help_text="Weight in percentage for this subject in the exam",
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exam", "subject")
        ordering = ["subject__name"]

    def __str__(self):
        return f"{self.subject.name} ({self.exam.name})"

    @property
    def average_score(self):
        avg = self.results.aggregate(avg_score=Avg("score"))["avg_score"]
        return round(avg, 2) if avg else None

    # @property
    # def pass_rate(self):
    #     if not self.pass_score:
    #         return None

    #     total = self.results.count()
    #     passed = self.results.filter(score__gte=self.pass_score).count()
    #     return round((passed / total) * 100, 2) if total > 0 else None

    @property
    def pass_rate(self):
        if not self.pass_score:
            return None

        results = self.results.filter(is_absent=False)
        total = results.count()
        if total == 0:
            return None

        passed = results.filter(score__gte=self.pass_score).count()
        return round((passed / total) * 100, 2)


class ExamResult(models.Model):
    """Results for a student in a particular exam subject"""

    exam_subject = models.ForeignKey(
        ExamSubject, on_delete=models.CASCADE, related_name="results"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="exam_results"
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        null=True,
        blank=True,
    )
    grade = models.CharField(max_length=10, blank=True, null=True)
    points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        null=True,
        blank=True,
    )
    remark = models.CharField(max_length=200, blank=True, null=True)
    teacher_comment = models.TextField(blank=True, null=True)
    is_absent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exam_subject", "student")
        ordering = ["student__last_name", "student__first_name"]

    def __str__(self):
        return f"{self.student} - {self.exam_subject.subject} ({self.score})"

    def save(self, *args, **kwargs):
        # Calculate grade and points if score is provided
        if self.score is not None and not self.is_absent:
            grading_system = self.exam_subject.exam.grading_system
            grade_range = grading_system.grade_ranges.filter(
                min_score__lte=self.score, max_score__gte=self.score
            ).first()

            if grade_range:
                self.grade = grade_range.grade
                self.points = grade_range.points
                self.remark = grade_range.remark
        elif self.is_absent:
            self.score = None
            self.grade = "ABS"
            self.points = None
            self.remark = "Absent"

        super().save(*args, **kwargs)

    def clean(self):
        if (
            ExamResult.objects.filter(
                exam_subject=self.exam_subject, student=self.student
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                "A result for this student and subject already exists"
            )
        super().clean()


class TermReport(models.Model):
    """Consolidated term report that combines multiple exams"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="term_reports"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="term_reports"
    )
    term = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=20)
    total_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        null=True,
        blank=True,
    )
    average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        null=True,
        blank=True,
    )
    overall_grade = models.CharField(max_length=10, blank=True, null=True)
    overall_position = models.PositiveIntegerField(null=True, blank=True)
    class_average = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        null=True,
        blank=True,
    )
    class_highest = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        null=True,
        blank=True,
    )
    class_lowest = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        null=True,
        blank=True,
    )
    principal_comment = models.TextField(blank=True, null=True)
    class_teacher_comment = models.TextField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "school_class", "term", "academic_year")
        ordering = ["-academic_year", "term", "student__last_name"]

    def __str__(self):
        return f"{self.student} - {self.term} {self.academic_year}"

    def clean(self):
        if (
            TermReport.objects.filter(
                student=self.student,
                school_class=self.school_class,
                term=self.term,
                academic_year=self.academic_year,
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError("A term report for this student already exists")
        super().clean()

    def calculate_results(self):
        # Get all exam results for this student in this term
        exam_results = ExamResult.objects.filter(
            exam_subject__exam__term=self.term,
            exam_subject__exam__academic_year=self.academic_year,
            exam_subject__exam__school_class=self.school_class,
            student=self.student,
            is_absent=False,
        ).select_related("exam_subject")

        if not exam_results.exists():
            return

        # Calculate weighted scores
        total_weighted_score = 0
        total_weight = 0
        subject_scores = []

        for result in exam_results:
            if result.score is not None:
                weight = result.exam_subject.weight
                weighted_score = (result.score / result.exam_subject.max_score) * weight
                total_weighted_score += weighted_score
                total_weight += weight
                subject_scores.append(result.score)

        if total_weight > 0:
            self.average_score = (total_weighted_score / total_weight) * 100
            self.total_score = sum(subject_scores)

            # Calculate class statistics
            class_results = (
                ExamResult.objects.filter(
                    exam_subject__exam__term=self.term,
                    exam_subject__exam__academic_year=self.academic_year,
                    exam_subject__exam__school_class=self.school_class,
                    is_absent=False,
                )
                .values("student")
                .annotate(avg_score=Avg("score"))
                .order_by("-avg_score")
            )

            # Get position
            student_avg = self.average_score
            position = 1
            for res in class_results:
                if res["avg_score"] > student_avg:
                    position += 1
                else:
                    break

            self.overall_position = position

            # Class statistics
            self.class_average = class_results.aggregate(avg=Avg("avg_score"))["avg"]
            self.class_highest = class_results.aggregate(max=Max("avg_score"))["max"]
            self.class_lowest = class_results.aggregate(min=Min("avg_score"))["min"]

            # Calculate overall grade
            grading_system = exam_results.first().exam_subject.exam.grading_system
            grade_range = grading_system.grade_ranges.filter(
                min_score__lte=self.average_score, max_score__gte=self.average_score
            ).first()

            if grade_range:
                self.overall_grade = grade_range.grade

        self.save()


class ExamConsolidationRule(models.Model):
    """Defines how different exam types contribute to final term grades"""

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="consolidation_rules"
    )
    exam_type = models.ForeignKey(
        ExamType, on_delete=models.CASCADE, related_name="consolidation_rules"
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight in percentage for this exam type",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("school", "exam_type")
        ordering = ["-weight"]

    def __str__(self):
        return f"{self.exam_type.name} ({self.weight}%) - {self.school.name}"


class ConsolidatedReport(models.Model):
    """Stores final consolidated term results for students"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="consolidated_reports"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="consolidated_reports"
    )
    term = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=20)
    total_score = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(0)]
    )
    average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    overall_grade = models.CharField(max_length=10)
    overall_position = models.PositiveIntegerField()
    details = models.JSONField()  # Stores breakdown of exam contributions
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "school_class", "term", "academic_year")
        ordering = ["-academic_year", "term", "overall_position"]

    def __str__(self):
        return f"{self.student} - Term {self.term} {self.academic_year}"
