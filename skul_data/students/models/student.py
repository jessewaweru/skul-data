from django.db import models
from django.utils import timezone


class StudentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    GRADUATED = "GRADUATED", "Graduated"
    LEFT = "LEFT", "Left"
    SUSPENDED = "SUSPENDED", "Suspended"


class Student(models.Model):
    first_name = models.CharField(max_length=250)
    middle_name = models.CharField(max_length=250, blank=True, null=True)
    last_name = models.CharField(max_length=250)
    date_of_birth = models.DateField()
    admission_date = models.DateField(default=timezone.now)
    admission_number = models.CharField(
        max_length=50, unique=True, null=True, blank=True
    )
    gender = models.CharField(
        max_length=10,
        choices=[("M", "Male"), ("F", "Female"), ("N", "Not Specified")],
        default="N",
    )
    photo = models.ImageField(upload_to="student_photos/", blank=True, null=True)
    status = models.CharField(
        max_length=10, choices=StudentStatus.choices, default=StudentStatus.ACTIVE
    )

    # Relationships
    student_class = models.ForeignKey(
        "schools.SchoolClass",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="class_students",
    )
    subjects = models.ManyToManyField("students.Subject", related_name="students")
    parent = models.ForeignKey(
        "users.Parent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_students",
    )
    guardians = models.ManyToManyField(
        "users.Parent", related_name="guardian_students", blank=True
    )
    teacher = models.ForeignKey(
        "users.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_students",
    )
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="students",
        default=None,
    )
    # Additional Fields
    medical_notes = models.TextField(blank=True, null=True)
    special_needs = models.TextField(blank=True, null=True)
    performance_tier = models.CharField(
        max_length=1,
        choices=[
            ("A", "Top"),
            ("B", "Above Average"),
            ("C", "Average"),
            ("D", "Below Average"),
        ],
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    # Add soft delete fields
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        unique_together = ("first_name", "last_name", "date_of_birth", "school")
        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["admission_number"]),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.admission_number}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        today = timezone.now().date()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def promote(self, new_class):
        """Promote student to a new class"""
        if self.status != StudentStatus.ACTIVE:
            raise ValueError("Only active students can be promoted")
        self.student_class = new_class
        self.save()

    def transfer(self, new_school):
        """Transfer student to a new school"""
        self.school = new_school
        self.save()

    def graduate(self):
        """Mark student as graduated"""
        self.status = StudentStatus.GRADUATED
        self.save()

    def deactivate(self, reason):
        """Soft delete student with a reason"""
        self.is_active = False
        self.status = StudentStatus.LEFT
        self.deleted_at = timezone.now()
        self.deletion_reason = reason
        self.save()

        StudentStatusChange.objects.create(
            student=self,
            from_status=StudentStatus.ACTIVE,
            to_status=StudentStatus.LEFT,
            reason=reason,
            changed_by=self.teacher.user if self.teacher else None,
        )

    @property
    def phone_number(self):
        """Get primary parent's phone number"""
        if self.parent:
            return self.parent.user.phone_number
        return (
            self.guardians.first().user.phone_number
            if self.guardians.exists()
            else None
        )

    @property
    def email(self):
        """Get primary parent's email"""
        if self.parent:
            return self.parent.user.email
        return self.guardians.first().user.email if self.guardians.exists() else None

    @property
    def address(self):
        """Get primary parent's address"""
        if self.parent:
            return self.parent.user.address
        return self.guardians.first().user.address if self.guardians.exists() else None


class StudentStatusChange(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="status_changes"
    )
    from_status = models.CharField(max_length=10, choices=StudentStatus.choices)
    to_status = models.CharField(max_length=10, choices=StudentStatus.choices)
    reason = models.TextField()
    changed_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.student} - {self.from_status} to {self.to_status}"


class StudentDocument(models.Model):
    DOCUMENT_TYPES = [
        ("REPORT_CARD", "Report Card"),
        ("BIRTH_CERTIFICATE", "Birth Certificate"),
        ("MEDICAL", "Medical Record"),
        ("TRANSFER", "Transfer Certificate"),
        ("OTHER", "Other"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to="student_documents/%Y/%m/%d/")
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_student_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.title} for {self.student}"


class StudentNote(models.Model):
    NOTE_TYPES = [
        ("ACADEMIC", "Academic"),
        ("BEHAVIOR", "Behavior"),
        ("MEDICAL", "Medical"),
        ("OTHER", "Other"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="notes")
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES)
    content = models.TextField()
    created_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, related_name="student_notes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_private = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_note_type_display()} note for {self.student}"


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="E.g., MATH101")
    description = models.TextField(blank=True, null=True)
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="subjects",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name
