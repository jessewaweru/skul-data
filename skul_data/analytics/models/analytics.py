from django.db import models
from skul_data.schools.models.school import School
from django.contrib.auth.models import User
from django.db.models import JSONField
from django.conf import settings


class AnalyticsDashboard(models.Model):
    """Stores custom dashboard configurations for users"""

    name = models.CharField(max_length=100)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_default = models.BooleanField(default=False)
    config = JSONField(help_text="Dashboard widget configuration")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "school")
        ordering = ["-is_default", "name"]

    def __str__(self):
        return f"{self.name} ({self.school.name})"


class CachedAnalytics(models.Model):
    """Stores pre-computed analytics data for performance"""

    school = models.ForeignKey(School, on_delete=models.CASCADE)
    analytics_type = models.CharField(max_length=50)
    data = JSONField()
    computed_at = models.DateTimeField(auto_now=True)
    valid_until = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["school", "analytics_type"]),
        ]
        verbose_name_plural = "Cached analytics"

    def __str__(self):
        return f"{self.analytics_type} for {self.school.name}"


class AnalyticsAlert(models.Model):
    """System-generated alerts based on analytics"""

    ALERT_TYPES = [
        ("ATTENDANCE", "Attendance Alert"),
        ("PERFORMANCE", "Performance Alert"),
        ("REPORT", "Report Alert"),
        ("DOCUMENT", "Document Alert"),
        ("SYSTEM", "System Alert"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_model = models.CharField(max_length=50, null=True, blank=True)
    related_id = models.PositiveIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.title}"
