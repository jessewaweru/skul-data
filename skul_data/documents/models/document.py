from django.db import models
from skul_data.schools.models.school import School
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.superuser import SuperUser


class DocumentCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    is_custom = models.BooleanField(
        default=False
    )  # True if added by school, False if predefined
    school = models.ForeignKey(
        "schools.School", null=True, blank=True, on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name


class Document(models.Model):
    CATEGORY_CHOICES = [
        ("Exam", "Exam"),
        ("Salary", "Salary"),
        ("Report", "Report"),
        ("Other", "Other"),
    ]
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to="documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # Restricting uploads to only SuperUser or Teacher
    uploaded_by_superuser = models.ForeignKey(
        SuperUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_by_teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.uploaded_by_superuser and not self.uploaded_by_teacher:
            raise ValueError("A document must be uploaded by a SuperUser or a Teacher.")
        super().save(*args, **kwargs)

    def __str__(self):
        uploader = self.uploaded_by_superuser or self.uploaded_by_teacher
        return f"{self.title} uploaded by {uploader}"
