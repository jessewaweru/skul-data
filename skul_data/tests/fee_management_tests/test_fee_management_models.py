from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from skul_data.tests.fee_management_tests.test_helpers import (
    create_test_fee_structure,
    create_test_fee_record,
    create_test_fee_payment,
    create_test_fee_upload_log,
    create_test_fee_invoice_template,
    create_test_fee_reminder,
    create_test_school_with_fee_data,
)
import random
from skul_data.fee_management.models.fee_management import (
    FeeStructure,
    FeeRecord,
    FeePayment,
    FeeInvoiceTemplate,
    FeeReminder,
    FeeUploadLog,
)
from skul_data.users.models.parent import Parent
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.base_user import User
from skul_data.students.models.student import Student
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from django.test import TransactionTestCase
from django.db import transaction, IntegrityError


class FeeStructureModelTest(TransactionTestCase):
    def setUp(self):
        # Clear database before each test
        self._clear_all_data()

        # Create fresh data for each test to avoid conflicts
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.school_class = self.test_data["class"]
        self.teacher = self.test_data["teacher"]
        self.parent = self.test_data["parent"]
        self.student = self.test_data["student"]

    def tearDown(self):
        # Clean up all created objects
        self._clear_all_data()

    def _clear_all_data(self):
        """Clear all test data from database"""
        # Delete in reverse dependency order
        FeePayment.objects.all().delete()
        FeeRecord.objects.all().delete()
        FeeStructure.objects.all().delete()
        FeeUploadLog.objects.all().delete()
        FeeInvoiceTemplate.objects.all().delete()
        FeeReminder.objects.all().delete()
        # Clear related models
        Student.objects.all().delete()
        Parent.objects.all().delete()
        Teacher.objects.all().delete()
        SchoolClass.objects.all().delete()
        School.objects.all().delete()
        User.objects.all().delete()

    def test_create_fee_structure(self):
        # Create a new fee structure for this specific test
        fee_structure = create_test_fee_structure(
            self.school,
            self.school_class,
            term="term_1",
            year=str(timezone.now().year + 2),  # Use different year to avoid conflicts
        )
        self.assertEqual(fee_structure.school, self.school)
        self.assertEqual(fee_structure.school_class, self.school_class)
        self.assertEqual(fee_structure.term, "term_1")
        self.assertEqual(fee_structure.amount, Decimal("15000.00"))
        self.assertTrue(fee_structure.is_active)
        self.assertEqual(
            str(fee_structure),
            f"{self.school_class} - Term 1 {timezone.now().year + 2}: Ksh 15000.00",
        )

    def test_unique_together_constraint(self):
        # Create first fee structure with specific parameters
        term = "term_1"  # Use valid choice that fits in 20 chars
        year = str(timezone.now().year + 100)  # Use far future year

        # Create first structure
        create_test_fee_structure(self.school, self.school_class, term=term, year=year)

        # Try to create duplicate - this should raise IntegrityError
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                create_test_fee_structure(
                    self.school, self.school_class, term=term, year=year
                )

    def test_total_students_property(self):
        # Add student to class
        self.school_class.students.add(self.student)

        # Create fresh fee structure
        fee_structure = create_test_fee_structure(
            self.school,
            self.school_class,
            term="students_test",
            year=str(timezone.now().year + 4),
        )

        self.assertEqual(fee_structure.total_students, 1)

    def test_expected_revenue_property(self):
        # Add student to class first
        self.school_class.students.add(self.student)

        fee_structure = create_test_fee_structure(
            self.school,
            self.school_class,
            term="revenue_test",
            year=str(timezone.now().year + 5),
        )
        expected = fee_structure.amount * fee_structure.total_students
        self.assertEqual(fee_structure.expected_revenue, expected)

    def test_due_date_validation(self):
        """
        Note: This test will only pass if you add the clean() method to your FeeStructure model.
        Add this to your FeeStructure model:

        def clean(self):
            from django.core.exceptions import ValidationError
            from django.utils import timezone

            if self.due_date and self.due_date < timezone.now().date():
                raise ValidationError("Due date cannot be in the past.")

            super().clean()
        """
        # Create a fee structure with past due date
        fee_structure = FeeStructure(
            school=self.school,
            school_class=self.school_class,
            term="validation_test",
            year=str(timezone.now().year + 6),
            amount=Decimal("15000.00"),
            due_date=timezone.now().date() - timedelta(days=1),
            is_active=True,
        )

        # This should raise ValidationError if you implement the clean method
        with self.assertRaises(ValidationError):
            fee_structure.full_clean()


class FeeRecordModelTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.student = self.test_data["student"]
        self.parent = self.test_data["parent"]
        self.fee_structure = self.test_data["fee_structure"]

    def test_create_fee_record(self):
        # Create a new fee structure to avoid conflicts
        new_fee_structure = create_test_fee_structure(
            self.fee_structure.school,
            self.fee_structure.school_class,
            term="record_test_term",
            year=str(int(self.fee_structure.year) + 1),
        )

        fee_record = create_test_fee_record(
            self.student, self.parent, new_fee_structure
        )

        self.assertEqual(fee_record.fee_structure.id, new_fee_structure.id)
        self.assertEqual(fee_record.student, self.student)
        self.assertEqual(fee_record.parent, self.parent)

    def test_payment_status_updates(self):
        # Create a new fee structure to avoid conflicts
        new_fee_structure = create_test_fee_structure(
            self.fee_structure.school,
            self.fee_structure.school_class,
            term="status_test_term",
            year=str(int(self.fee_structure.year) + 2),
        )

        fee_record = create_test_fee_record(
            self.student, self.parent, new_fee_structure
        )

        # Partially paid
        fee_record.amount_paid = Decimal("5000.00")
        fee_record.save()
        self.assertEqual(fee_record.payment_status, "partial")
        self.assertEqual(fee_record.balance, Decimal("10000.00"))

        # Fully paid
        fee_record.amount_paid = new_fee_structure.amount
        fee_record.save()
        self.assertEqual(fee_record.payment_status, "paid")
        self.assertEqual(fee_record.balance, Decimal("0.00"))

        # Overdue
        fee_record.amount_paid = Decimal("5000.00")
        fee_record.due_date = timezone.now().date() - timedelta(days=1)
        fee_record.save()
        self.assertEqual(fee_record.payment_status, "overdue")
        self.assertTrue(fee_record.is_overdue)

    def test_payment_percentage_property(self):
        # Create a new fee structure to avoid conflicts
        new_fee_structure = create_test_fee_structure(
            self.fee_structure.school,
            self.fee_structure.school_class,
            term="percentage_test_term",
            year=str(int(self.fee_structure.year) + 3),
        )

        fee_record = create_test_fee_record(
            self.student,
            self.parent,
            new_fee_structure,
            amount_paid=Decimal("7500.00"),
        )
        self.assertEqual(fee_record.payment_percentage, 50)

    def test_unique_together_constraint(self):
        # Create first fee record
        fee_record1 = create_test_fee_record(
            self.student, self.parent, self.fee_structure
        )

        # Try to create duplicate - should raise IntegrityError
        with self.assertRaises(IntegrityError):
            FeeRecord.objects.create(
                student=self.student,
                parent=self.parent,
                fee_structure=self.fee_structure,
                amount_owed=self.fee_structure.amount,
                amount_paid=Decimal("0.00"),
                due_date=self.fee_structure.due_date,
            )


class FeePaymentModelTest(TestCase):
    def setUp(self):
        # Create fresh test data for each test
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.student = self.test_data["student"]
        self.parent = self.test_data["parent"]
        self.fee_structure = self.test_data["fee_structure"]
        self.fee_record = self.test_data["fee_record"]

    def test_create_fee_payment(self):
        # Create a fresh fee record to avoid existing payments
        new_fee_structure = create_test_fee_structure(
            self.school,
            self.test_data["class"],
            term="payment_create_test",
            year=str(timezone.now().year + 50),
        )

        fee_record = create_test_fee_record(
            self.student,
            self.parent,
            new_fee_structure,
        )

        # Create fee payment with specific values that match test expectations
        fee_payment = create_test_fee_payment(
            fee_record,
            transaction_reference="MPESA12345",  # Specify expected value
            receipt_number="RCPT12345",
        )
        self.assertEqual(fee_payment.fee_record, fee_record)
        self.assertEqual(fee_payment.amount, Decimal("5000.00"))
        self.assertEqual(fee_payment.payment_method, "mpesa")
        self.assertEqual(fee_payment.transaction_reference, "MPESA12345")
        self.assertEqual(fee_payment.receipt_number, "RCPT12345")
        self.assertTrue(fee_payment.is_confirmed)
        self.assertEqual(
            str(fee_payment),
            f"Payment of Ksh 5000.00 for {fee_record}",
        )

    def test_payment_updates_fee_record(self):
        # Create a completely fresh fee structure and record to avoid conflicts
        new_fee_structure = create_test_fee_structure(
            self.school,
            self.test_data["class"],
            term="term_2",
            year=str(timezone.now().year + 10),
        )

        # Create a completely new fee record without any existing payments
        fee_record = FeeRecord.objects.create(
            student=self.student,
            parent=self.parent,
            fee_structure=new_fee_structure,
            amount_owed=Decimal("15000.00"),
            amount_paid=Decimal("0.00"),
            due_date=new_fee_structure.due_date,
        )

        # Debug: Check if there are any existing payments
        existing_payments = FeePayment.objects.filter(fee_record=fee_record)
        print(f"Existing payments before: {existing_payments.count()}")
        print(f"Initial amount_paid: {fee_record.amount_paid}")

        # Verify initial state
        self.assertEqual(fee_record.amount_paid, Decimal("0.00"))

        # Make payment
        payment_amount = Decimal("5000.00")
        fee_payment = FeePayment.objects.create(
            fee_record=fee_record,
            amount=payment_amount,
            payment_method="mpesa",
            transaction_reference="TEST12345",
            receipt_number="RCPT12345",
            is_confirmed=True,
        )

        # Debug: Check payments after
        all_payments = FeePayment.objects.filter(fee_record=fee_record)
        print(f"Total payments after: {all_payments.count()}")
        print(f"Payment amounts: {[p.amount for p in all_payments]}")

        # Refresh from db
        fee_record.refresh_from_db()
        print(f"Final amount_paid: {fee_record.amount_paid}")

        # Test assertions
        self.assertEqual(fee_record.amount_paid, payment_amount)
        self.assertEqual(fee_record.balance, Decimal("10000.00"))


class FeeUploadLogModelTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.admin = self.test_data["admin"]

    def test_create_fee_upload_log(self):
        upload_log = create_test_fee_upload_log(self.school, self.admin)
        self.assertEqual(upload_log.school, self.school)
        self.assertEqual(upload_log.uploaded_by, self.admin)
        self.assertEqual(upload_log.term, "term_1")
        self.assertEqual(upload_log.status, "pending")
        self.assertEqual(upload_log.total_records, 0)
        self.assertEqual(
            str(upload_log),
            f"Fee Upload for {upload_log.school_class} - Term 1 {timezone.now().year}",
        )


class FeeReminderModelTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.fee_record = self.test_data["fee_record"]
        self.admin = self.test_data["admin"]

    def test_create_fee_reminder(self):
        reminder = create_test_fee_reminder(self.fee_record, self.admin)
        self.assertEqual(reminder.fee_record, self.fee_record)
        self.assertEqual(reminder.sent_via, "email")
        self.assertEqual(reminder.message, "Please pay your fees")
        self.assertEqual(reminder.sent_by, self.admin)
        self.assertTrue(reminder.is_successful)
        self.assertEqual(
            str(reminder),
            f"Reminder for {self.fee_record} sent via email",
        )


class FeeInvoiceTemplateModelTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]

    def test_create_fee_invoice_template(self):
        # Create template with specific name that matches test expectation
        template = create_test_fee_invoice_template(
            self.school, name="Default Template"  # Specify expected name
        )
        self.assertEqual(template.name, "Default Template")
        self.assertEqual(template.school, self.school)
        self.assertTrue(template.is_active)


# python manage.py test skul_data.tests.fee_management_tests.test_fee_management_models
