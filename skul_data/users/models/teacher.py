from django.db import models
from .base_user import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class Teacher(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("ON_LEAVE", "On Leave"),
        ("SUSPENDED", "Suspended"),
        ("TERMINATED", "Terminated"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="teacher_profile"
    )
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="teachers"
    )
    subjects_taught = models.ManyToManyField(
        "students.Subject", related_name="teachers", blank=True
    )
    assigned_classes = models.ManyToManyField(
        "schools.SchoolClass", related_name="teachers", blank=True
    )
    phone_number = models.CharField(max_length=21, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    hire_date = models.DateField(default=timezone.now)
    termination_date = models.DateField(null=True, blank=True)
    qualification = models.CharField(max_length=255, blank=True, null=True)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    bio = models.TextField(blank=True, null=True)
    office_location = models.CharField(max_length=100, blank=True, null=True)
    office_hours = models.CharField(max_length=255, blank=True, null=True)
    is_class_teacher = models.BooleanField(default=False)
    is_department_head = models.BooleanField(default=False)
    payroll_number = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]
        verbose_name = "Teacher"
        verbose_name_plural = "Teachers"

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.school.name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            self.user.user_type = User.TEACHER
            self.user.save()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email

    # @property
    # def phone_number(self):
    #     return self.user.phone_number

    @property
    def last_login(self):
        return self.user.last_login

    @property
    def active_students_count(self):
        from skul_data.students.models.student import Student, StudentStatus

        return Student.objects.filter(
            teacher=self, status=StudentStatus.ACTIVE, is_active=True
        ).count()

    @property
    def current_classes(self):
        current_year = timezone.now().year
        return self.assigned_classes.filter(academic_year__contains=str(current_year))


class TeacherWorkload(models.Model):
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="workloads"
    )
    school_class = models.ForeignKey("schools.SchoolClass", on_delete=models.CASCADE)
    subject = models.ForeignKey("students.Subject", on_delete=models.CASCADE)
    hours_per_week = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    term = models.CharField(max_length=20)
    school_year = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("teacher", "school_class", "subject", "term", "school_year")
        ordering = ["school_year", "term", "teacher"]

    def __str__(self):
        return f"{self.teacher} - {self.subject} ({self.hours_per_week} hrs/wk)"


class TeacherAttendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),
        ("ON_LEAVE", "On Leave"),
    ]

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("teacher", "date")
        ordering = ["-date"]
        verbose_name_plural = "Teacher attendances"

    def __str__(self):
        return f"{self.teacher} - {self.date}: {self.get_status_display()}"


class TeacherDocument(models.Model):
    DOCUMENT_TYPES = [
        ("QUALIFICATION", "Qualification"),
        ("CV", "Curriculum Vitae"),
        ("CONTRACT", "Contract"),
        ("CERTIFICATE", "Certificate"),
        ("EVALUATION", "Performance Evaluation"),
        ("OTHER", "Other"),
    ]

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to="teacher_documents/%Y/%m/%d/")
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="uploaded_teacher_docs"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_confidential = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()}) for {self.teacher}"
