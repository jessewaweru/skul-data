from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.conf import settings
from model_utils import Choices
from decimal import Decimal
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Student


class FeeStructure(models.Model):
    """Defines the fee amounts for each class/term combination"""

    TERM_CHOICES = [
        ("term_1", "Term 1"),
        ("term_2", "Term 2"),
        ("term_3", "Term 3"),
    ]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="fee_structures"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="fee_structures"
    )
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    year = models.CharField(max_length=4)  # e.g. "2023"
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("school_class", "term", "year")
        ordering = ["school_class", "term", "year"]

    def __str__(self):
        return f"{self.school_class} - {self.get_term_display()} {self.year}: Ksh {self.amount}"

    @property
    def total_students(self):
        return self.school_class.students.count()

    @property
    def expected_revenue(self):
        return self.amount * self.total_students

    def clean(self):
        """Custom validation for FeeStructure model"""
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        # Validate that due_date is not in the past
        if self.due_date and self.due_date < timezone.now().date():
            raise ValidationError("Due date cannot be in the past.")

        super().clean()


class FeeRecord(models.Model):
    """Tracks fees owed and paid for each student"""

    PAYMENT_STATUS = Choices(
        ("unpaid", "Unpaid"),
        ("partial", "Partially Paid"),
        ("paid", "Fully Paid"),
        ("overdue", "Overdue"),
    )

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="fee_records"
    )
    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name="fee_records"
    )
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.CASCADE, related_name="fee_records"
    )
    amount_owed = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS, default=PAYMENT_STATUS.unpaid
    )
    due_date = models.DateField()
    is_overdue = models.BooleanField(default=False)
    last_payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "fee_structure")
        ordering = ["-due_date", "payment_status"]
        indexes = [
            models.Index(fields=["payment_status"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["is_overdue"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.fee_structure}: {self.payment_status}"

    def save(self, *args, **kwargs):
        # Calculate balance
        self.balance = self.amount_owed - self.amount_paid

        # Update payment status
        if self.amount_paid <= 0:
            self.payment_status = self.PAYMENT_STATUS.unpaid
        elif self.balance <= 0:
            self.payment_status = self.PAYMENT_STATUS.paid
        else:
            self.payment_status = self.PAYMENT_STATUS.partial

        # Check if overdue
        self.is_overdue = self.balance > 0 and timezone.now().date() > self.due_date
        if self.is_overdue and self.payment_status != self.PAYMENT_STATUS.overdue:
            self.payment_status = self.PAYMENT_STATUS.overdue

        super().save(*args, **kwargs)

    @property
    def payment_percentage(self):
        if self.amount_owed == 0:
            return 100
        return (self.amount_paid / self.amount_owed) * 100


class FeePayment(models.Model):
    """Records individual payments made towards a fee record"""

    PAYMENT_METHODS = Choices(
        ("mpesa", "M-PESA"),
        ("bank", "Bank Transfer"),
        ("cash", "Cash"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    )

    fee_record = models.ForeignKey(
        FeeRecord, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    receipt_image = models.ImageField(upload_to="fee_receipts/", blank=True, null=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_payments",
    )
    is_confirmed = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    payment_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date"]

    def __str__(self):
        return f"Payment of Ksh {self.amount} for {self.fee_record}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Update the fee record by recalculating total payments
        # This prevents double-counting issues
        from django.db.models import Sum

        fee_record = self.fee_record
        total_confirmed_payments = FeePayment.objects.filter(
            fee_record=fee_record, is_confirmed=True
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        # Update fee record with recalculated values
        fee_record.amount_paid = total_confirmed_payments
        fee_record.last_payment_date = self.payment_date
        fee_record.save()


class FeeUploadLog(models.Model):
    """Tracks CSV uploads for bulk fee assignments"""

    UPLOAD_STATUS = Choices(
        ("pending", "Pending Processing"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="fee_upload_logs"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="fee_uploads",
    )
    file = models.FileField(upload_to="fee_uploads/")
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.SET_NULL, null=True, blank=True
    )
    term = models.CharField(max_length=20, choices=FeeStructure.TERM_CHOICES)
    year = models.CharField(max_length=4)
    status = models.CharField(
        max_length=20, choices=UPLOAD_STATUS, default=UPLOAD_STATUS.pending
    )
    total_records = models.PositiveIntegerField(default=0)
    successful_records = models.PositiveIntegerField(default=0)
    failed_records = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Fee Upload for {self.school_class} - {self.get_term_display()} {self.year}"


class FeeInvoiceTemplate(models.Model):
    """Stores customizable fee invoice templates for schools"""

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="fee_invoice_templates"
    )
    name = models.CharField(max_length=100)
    template_file = models.FileField(upload_to="fee_invoice_templates/")
    is_active = models.BooleanField(default=True)
    header_html = models.TextField(
        help_text="HTML for invoice header (school logo, name, etc.)"
    )
    footer_html = models.TextField(
        help_text="HTML for invoice footer (payment instructions, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice Template - {self.name} ({self.school})"


class FeeReminder(models.Model):
    """Tracks fee reminders sent to parents"""

    fee_record = models.ForeignKey(
        FeeRecord, on_delete=models.CASCADE, related_name="reminders"
    )
    sent_via = models.CharField(
        max_length=20, choices=[("email", "Email"), ("sms", "SMS"), ("both", "Both")]
    )
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_fee_reminders",
    )
    is_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Reminder for {self.fee_record} sent via {self.sent_via}"
