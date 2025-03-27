from django.db import models
from skul_data.schools.models.school import School


class SalaryRecord(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="salary_records"
    )
    faculty_name = models.CharField(max_length=255)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.faculty_name} - {self.amount_paid} ({self.payment_date})"
