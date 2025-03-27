from django.db import models
from skul_data.schools.models.school import School
from skul_data.users.models.teacher import Teacher
from skul_data.students.models.student import Student


class AcademicRecord(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="academic_records"
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records_entered",
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    subjects = models.CharField(max_length=300)
    grade = models.CharField(max_length=3)
    term = models.CharField(max_length=20)  # Example: "Term 1, 2024"
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.first_name} - {self.subjects} - {self.term}"
