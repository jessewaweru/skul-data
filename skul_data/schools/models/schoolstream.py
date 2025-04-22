from django.db import models
from skul_data.schools.models.school import School


class SchoolStream(models.Model):
    """Custom stream names defined by each school"""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="streams")
    name = models.CharField(max_length=50)  # Just the base name like "West", "Science"
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("school", "name")  # Only unique within same school
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.school})"
