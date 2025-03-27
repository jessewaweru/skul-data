from django.db import models
from .student import Student
from users.models.teacher import Teacher
from skul_data.schools.models.school import School


class StudentRecord(models.Model):
    # Storing academic reports of students
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="reports"
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_reports",
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_reports"
    )
    file = models.FileField(upload_to="reports/")
    term = models.CharField(max_length=20)  # Example: "Term 1, 2024"
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f" Report for {self.student.first_name}{self.student.last_name} - {self.term}"
