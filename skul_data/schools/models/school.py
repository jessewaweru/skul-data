from django.db import models
from django.conf import settings
from skul_data.students.models.student import Student
import random
from datetime import timedelta


class School(models.Model):
    SCHOOL_TYPES = [
        ("PRE", "Pre-school"),
        ("PRI", "Primary"),
        ("SEC", "Secondary"),
        ("HS", "High School"),
    ]

    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=3, choices=SCHOOL_TYPES, default="PRI")
    motto = models.CharField(max_length=255, blank=True)
    founded_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=300, blank=True, null=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, default="Kenya")
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField()
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="school_logos/", null=True, blank=True)
    timezone = models.CharField(max_length=50, default="Africa/Nairobi")

    # Academic Structure
    academic_year_structure = models.CharField(
        max_length=20,
        choices=[("SEMESTER", "Semester"), ("TERM", "Term"), ("QUARTER", "Quarter")],
        default="TERM",
    )

    current_term = models.CharField(
        max_length=20,
        choices=[("term_1", "Term 1"), ("term_2", "Term 2"), ("term_3", "Term 3")],
        null=True,
        blank=True,
    )
    term_start_date = models.DateField(null=True, blank=True)
    term_end_date = models.DateField(null=True, blank=True)

    current_school_year = models.CharField(max_length=20, null=True, blank=True)

    # Relationships
    schooladmin = models.OneToOneField(
        "users.User",
        on_delete=models.PROTECT,
        related_name="administered_school",
        default=None,
        null=True,
        blank=True,
    )
    # Status
    is_active = models.BooleanField(default=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("manage_school", "Can manage all school operations"),
            ("view_dashboard", "Can view school dashboard"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"{self.name[:3].upper()}{random.randint(100,999)}"
        super().save(*args, **kwargs)


class SchoolSubscription(models.Model):
    SUBSCRIPTION_PLANS = [
        ("BASIC", "Basic"),
        ("STANDARD", "Standard"),
        ("ADVANCED", "Advanced"),
    ]

    PAYMENT_METHODS = [
        ("MPESA", "M-Pesa"),
        ("CARD", "Credit/Debit Card"),
        ("BANK", "Bank Transfer"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("PENDING", "Pending Payment"),
        ("EXPIRED", "Expired"),
        ("CANCELLED", "Cancelled"),
    ]

    school = models.OneToOneField(
        School, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, default="BASIC")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    last_payment_date = models.DateField(null=True, blank=True)
    next_payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHODS, default="MPESA"
    )

    class Meta:
        ordering = ["-end_date"]

    def __str__(self):
        return f"{self.school.name} - {self.get_plan_display()} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.pk:  # New subscription
            if self.plan == "BASIC":
                default_duration = 30  # days
            elif self.plan == "STANDARD":
                default_duration = 365  # days
            else:  # ADVANCED
                default_duration = 365  # days

            from django.utils import timezone

            self.start_date = timezone.now().date()
            self.end_date = self.start_date + timedelta(days=default_duration)
            self.next_payment_date = self.end_date - timedelta(
                days=7
            )  # Notify 1 week before

        super().save(*args, **kwargs)


class SecurityLog(models.Model):
    ACTION_TYPES = [
        ("LOGIN", "User Login"),
        ("LOGOUT", "User Logout"),
        ("PASSWORD_CHANGE", "Password Changed"),
        ("PROFILE_UPDATE", "Profile Updated"),
        ("DEVICE_CHANGE", "New Device Login"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_logs"
    )
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255)
    location = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user} - {self.get_action_type_display()} at {self.timestamp}"
