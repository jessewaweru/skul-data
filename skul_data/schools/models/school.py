from django.db import models
from django.conf import settings
from skul_data.students.models.student import Student
from skul_data.users.models.superuser import SuperUser


class School(models.Model):
    name = models.CharField(max_length=255, unique=True)
    level = models.CharField(max_length=50, default="Primary")
    code = models.CharField(max_length=20, unique=True, default="SKUD000")
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15, default="0700000000")
    superuser_profile = models.OneToOneField(
        SuperUser, on_delete=models.CASCADE, null=True, blank=True
    )
    created_by = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="school"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    name = models.CharField(max_length=100, unique=True)  # e.g., "Grade 6A", "Form 2B"
    grade_level = models.CharField(
        max_length=20,
        choices=[
            ("Kindergarten", "Kindergarten"),
            ("Grade 1", "Grade 1"),
            ("Grade 2", "Grade 2"),
            ("Grade 3", "Grade 3"),
            ("Grade 4", "Grade 4"),
            ("Grade 5", "Grade 5"),
            ("Grade 6", "Grade 6"),
            ("Form 1", "Form 1"),
            ("Form 2", "Form 2"),
            ("Form 3", "Form 3"),
            ("Form 4", "Form 4"),
        ],
    )
    class_teacher = models.ForeignKey(
        "users.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classes_taught",
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    students = models.ManyToManyField(Student, related_name="classes")
    subjects = models.JSONField(default=list, blank=True)
    year = models.PositiveIntegerField()
    room_number = models.CharField(
        max_length=10, blank=True, null=True
    )  # Physical classroom location
    timetable = models.FileField(
        upload_to="timetables/", blank=True, null=True
    )  # Upload class timetable
    created_at = models.DateTimeField(auto_now_add=True)  # Track when class was created
    updated_at = models.DateTimeField(auto_now=True)  # Track last update

    def __str__(self):
        return f"{self.name} - {self.grade_level} ({self.year})"
