# reports/models.py
import uuid
from django.db import models
from django.db.models import JSONField
from django.core.exceptions import ValidationError
from django.utils import timezone
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Student
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.base_user import User


class ReportTemplate(models.Model):
    """Predefined templates for different types of reports"""

    TEMPLATE_TYPES = [
        ("ACADEMIC", "Academic Performance"),
        ("ATTENDANCE", "Attendance"),
        ("BEHAVIOR", "Behavior"),
        ("PAYROLL", "Payroll"),
        ("ENROLLMENT", "Enrollment"),
        ("FINANCE", "Finance"),
        ("CUSTOM", "Custom"),
    ]
    REPORT_FORMATS = [
        ("PDF", "PDF"),
        ("EXCEL", "Excel"),
        ("HTML", "HTML"),
    ]
    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    description = models.TextField(blank=True, null=True)
    content = JSONField(help_text="JSON structure defining the report template")
    is_system = models.BooleanField(default=False, help_text="System-wide template")
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)
    preferred_format = models.CharField(
        max_length=10, choices=REPORT_FORMATS, default="PDF"
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "school")
        ordering = ["-is_system", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def clean(self):
        if self.is_system and self.school:
            raise ValidationError(
                "System templates cannot be associated with a specific school"
            )


class GeneratedReport(models.Model):
    """Reports that have been generated"""

    REPORT_STATUS = [
        ("DRAFT", "Draft"),
        ("PUBLISHED", "Published"),
        ("ARCHIVED", "Archived"),
    ]

    REPORT_FORMATS = [
        ("PDF", "PDF"),
        ("EXCEL", "Excel"),
        ("HTML", "HTML"),
        ("CSV", "CSV"),
    ]

    title = models.CharField(max_length=255)
    report_type = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=REPORT_STATUS, default="DRAFT")
    file = models.FileField(upload_to="reports/%Y/%m/%d/", null=True, blank=True)
    file_format = models.CharField(
        max_length=10, choices=REPORT_FORMATS, null=True, blank=True
    )
    data = JSONField(help_text="JSON data used to generate the report")
    parameters = JSONField(help_text="Parameters used to generate the report")
    notes = models.TextField(blank=True, null=True)
    # Access control fields
    is_public = models.BooleanField(default=False)
    allowed_roles = models.ManyToManyField("users.Role", blank=True)
    allowed_users = models.ManyToManyField(
        User, related_name="allowed_reports", blank=True
    )
    # Related entities (optional)
    related_class = models.ForeignKey(
        SchoolClass, on_delete=models.SET_NULL, null=True, blank=True
    )
    related_students = models.ManyToManyField(Student, blank=True)
    related_teachers = models.ManyToManyField(Teacher, blank=True)
    # Approval workflow
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        related_name="approved_reports",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    # Expiry/validity
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-generated_at"]
        permissions = [
            ("bulk_generate_report", "Can generate reports in bulk"),
            ("approve_report", "Can approve reports"),
        ]

    def __str__(self):
        return f"{self.title} - {self.school.name}"

    @property
    def is_valid(self):
        if self.valid_until:
            return timezone.now() < self.valid_until
        return True

    @property
    def is_approved(self):
        if not self.requires_approval:
            return True
        return self.approved_by is not None


class ReportAccessLog(models.Model):
    """Tracks who has accessed which reports"""

    report = models.ForeignKey(GeneratedReport, on_delete=models.CASCADE)
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    accessed_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(
        max_length=20,
        choices=[
            ("VIEWED", "Viewed"),
            ("DOWNLOADED", "Downloaded"),
            ("SHARED", "Shared"),
        ],
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-accessed_at"]

    def __str__(self):
        return f"{self.accessed_by} {self.action} {self.report} at {self.accessed_at}"


class GeneratedReportAccess(models.Model):
    """Tracks which users have access to which reports and when that access expires"""

    report = models.ForeignKey(
        "GeneratedReport", on_delete=models.CASCADE, related_name="access_grants"
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="report_accesses"
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("report", "user")
        verbose_name_plural = "Generated report accesses"

    def __str__(self):
        return f"{self.user} access to {self.report} (expires: {self.expires_at})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_accessed(self):
        return self.accessed_at is not None


class ReportSchedule(models.Model):
    """Scheduled automatic report generation"""

    FREQUENCY_CHOICES = [
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
        ("TERMLY", "Termly"),
        ("YEARLY", "Yearly"),
        ("CUSTOM", "Custom"),
    ]
    name = models.CharField(max_length=255)
    report_template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    custom_cron = models.CharField(
        max_length=100, blank=True, null=True, help_text="Custom cron expression"
    )
    recipients = models.ManyToManyField(
        User, related_name="scheduled_reports", blank=True
    )
    email_recipients = models.TextField(
        blank=True, null=True, help_text="Comma-separated email addresses"
    )
    parameters = JSONField(help_text="Parameters to use when generating the report")
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_run", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"

    def clean(self):
        if self.frequency == "CUSTOM" and not self.custom_cron:
            raise ValidationError("Custom frequency requires a cron expression")


class ReportNotification(models.Model):
    """Notifications sent when reports are generated"""

    report = models.ForeignKey(GeneratedReport, on_delete=models.CASCADE)
    sent_to = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    method = models.CharField(
        max_length=10,
        choices=[
            ("EMAIL", "Email"),
            ("IN_APP", "In-App"),
            ("BOTH", "Both"),
        ],
    )
    message = models.TextField()

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        recipient = self.sent_to.username if self.sent_to else self.email
        return f"Notification about {self.report} to {recipient}"


class AcademicReportConfig(models.Model):
    """Configuration for academic report generation-this model lets the school define when and how reports are auto-generated."""

    school = models.OneToOneField(School, on_delete=models.CASCADE)
    auto_generate_term_reports = models.BooleanField(default=True)
    days_after_term_to_generate = models.PositiveIntegerField(default=3)
    notify_parents_on_generation = models.BooleanField(default=True)
    parent_access_expiry_days = models.PositiveIntegerField(
        default=30, help_text="How many days parents can access term reports"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Academic Report Config for {self.school.name}"


class TermReportRequest(models.Model):
    """Track parent requests for student reports"""

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE)
    parent = models.ForeignKey("users.User", on_delete=models.CASCADE)
    term = models.CharField(max_length=50)
    school_year = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    generated_report = models.ForeignKey(
        "GeneratedReport", on_delete=models.SET_NULL, null=True, blank=True
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("student", "parent", "term", "school_year")

    def __str__(self):
        return (
            f"{self.parent} request for {self.student} ({self.term} {self.school_year})"
        )
