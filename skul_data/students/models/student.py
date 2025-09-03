from django.db import models
from django.utils import timezone
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from django.db.models import Max


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

    def deactivate(self, reason="No reason provided", user=None):
        """Soft delete student with reason"""
        old_status = self.status  # Store the old status

        self.is_active = False
        self.status = StudentStatus.LEFT
        self.deleted_at = timezone.now()
        self.deletion_reason = reason
        self.save()

        # Create StudentStatusChange record
        StudentStatusChange.objects.create(
            student=self,
            from_status=old_status,
            to_status=StudentStatus.LEFT,
            reason=reason,
            changed_by=user if user else None,
        )

        # Only log the action if user is provided (for direct model calls)
        # The viewset will handle its own logging
        if user:
            from skul_data.action_logs.utils.action_log import log_action
            from skul_data.action_logs.models.action_log import ActionCategory

            log_action(
                user,
                f"Changed student {self} status from ACTIVE to LEFT",
                ActionCategory.UPDATE,
                self,
                {"reason": reason, "previous_status": old_status},
            )

    @property
    def phone_number(self):
        """Get primary parent's phone number"""
        try:
            if self.parent:
                return self.parent.phone_number

            # Use a more efficient query to avoid recursion
            guardian = self.guardians.select_related("user").first()
            if guardian:
                return guardian.phone_number
        except Exception:
            # Return None if there's any error to prevent crashes
            return None
        return None

    @property
    def email(self):
        """Get primary parent's email"""
        try:
            if self.parent:
                return self.parent.user.email

            guardian = self.guardians.select_related("user").first()
            if guardian:
                return guardian.user.email
        except Exception:
            return None
        return None

    @property
    def address(self):
        """Get primary parent's address"""
        try:
            if self.parent:
                return self.parent.address

            guardian = self.guardians.first()
            if guardian:
                return guardian.address
        except Exception:
            return None
        return None


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

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:  # Only log for new creations
            log_action(
                self.changed_by,
                f"Changed student {self.student} status from {self.from_status} to {self.to_status}",
                ActionCategory.UPDATE,
                self.student,
                {
                    "change_id": self.id,
                    "reason": self.reason,
                    "from_status": self.from_status,
                    "to_status": self.to_status,
                    "changed_at": self.changed_at.isoformat(),
                },
            )


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


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"
    EXCUSED = "EXCUSED", "Excused Absence"


class StudentAttendance(models.Model):
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=10,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )
    recorded_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_attendance",
    )
    reason = models.TextField(
        blank=True, null=True, help_text="Reason for absence or late arrival"
    )
    time_in = models.TimeField(
        null=True, blank=True, help_text="Time student arrived if late"
    )
    notes = models.TextField(blank=True, null=True)

    # For administrative purposes
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "student__first_name"]
        unique_together = ["student", "date"]
        indexes = [
            models.Index(fields=["student", "date"]),
            models.Index(fields=["date", "status"]),
        ]

    def __str__(self):
        return f"{self.student.full_name} - {self.date} - {self.status}"

    def mark_present(self, recorded_by=None):
        """Mark student as present"""
        self.status = AttendanceStatus.PRESENT
        self.recorded_by = recorded_by
        self.save()

    def mark_absent(self, reason=None, recorded_by=None):
        """Mark student as absent"""
        self.status = AttendanceStatus.ABSENT
        self.reason = reason
        self.recorded_by = recorded_by
        self.save()

    def mark_late(self, time_in, reason=None, recorded_by=None):
        """Mark student as late"""
        self.status = AttendanceStatus.LATE
        self.time_in = time_in
        self.reason = reason
        self.recorded_by = recorded_by
        self.save()

    def mark_excused(self, reason, recorded_by=None):
        """Mark student as excused"""
        self.status = AttendanceStatus.EXCUSED
        self.reason = reason
        self.recorded_by = recorded_by
        self.save()

    @property
    def is_present(self):
        return self.status == AttendanceStatus.PRESENT

    @property
    def is_absent(self):
        return (
            self.status == AttendanceStatus.ABSENT
            or self.status == AttendanceStatus.EXCUSED
        )
