from django.db import models

# from skul_data.users.models.teacher import Teacher


class Student(models.Model):
    # from skul_data.users.models.parent import Parent

    first_name = models.CharField(max_length=250)
    last_name = models.CharField(max_length=250)
    date_of_birth = models.DateTimeField(auto_now_add=True)
    admission_date = models.DateTimeField(auto_now_add=True)
    student_class = models.ForeignKey(
        "schools.SchoolClass", on_delete=models.SET_NULL, null=True, blank=True
    )

    parent = models.ForeignKey(
        "users.Parent", on_delete=models.CASCADE, related_name="students"
    )
    teacher = models.ForeignKey(
        "users.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )

    def __str__(self):
        return f"{self.first_name}{self.last_name} - {self.student_class}"
