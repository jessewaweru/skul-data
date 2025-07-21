import io
from datetime import date, timedelta, datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from skul_data.tests.fee_management_tests.test_helpers import (
    create_test_school_with_fee_data,
    create_test_fee_upload_log,
    create_test_fee_record,
    create_test_fee_invoice_template,
)
from skul_data.fee_management.models.fee_management import (
    FeeReminder,
    FeeRecord,
    FeeStructure,
)
from skul_data.fee_management.utils.tasks import (
    process_fee_upload,
    send_fee_reminders,
    generate_fee_invoices,
    check_overdue_fees,
)
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile


class FeeManagementTasksTest(TestCase):
    def setUp(self):
        FeeRecord.objects.all().delete()
        FeeReminder.objects.all().delete()
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.admin = self.test_data["admin"]
        self.student = self.test_data["student"]
        self.parent = self.test_data["parent"]
        self.fee_structure = self.test_data["fee_structure"]
        self.fee_record = self.test_data["fee_record"]

    @patch("skul_data.fee_management.utils.tasks.EmailMessage")
    @patch("skul_data.fee_management.utils.tasks.render_to_string")
    def test_send_fee_reminders(self, mock_render_to_string, mock_email_message):
        # Setup test data
        self.parent.user.email = "test@example.com"
        self.parent.user.save()

        self.fee_record.amount_owed = Decimal("15000.00")
        self.fee_record.amount_paid = Decimal("0.00")
        self.fee_record.payment_status = "unpaid"
        self.fee_record.save()

        # Mock the term display value directly
        mock_term_display = "Term 1"
        self.fee_structure.get_term_display = lambda: mock_term_display

        # Mock email
        mock_email_instance = MagicMock()
        mock_email_message.return_value = mock_email_instance

        # Completely bypass template rendering
        mock_render_to_string.return_value = "Test email content"

        # Call the task
        result = send_fee_reminders(
            [str(self.fee_record.id)],
            "email",
            "Test reminder message",
            self.admin.id,
        )

        # Verify
        self.assertEqual(result["successful"], 1)
        self.assertEqual(result["failed"], 0)
        mock_email_message.assert_called_once()
        mock_email_instance.send.assert_called_once()

    @patch("django.core.files.storage.default_storage.open")
    def test_process_fee_upload(self, mock_storage_open):
        # Delete existing fee record
        FeeRecord.objects.filter(id=self.fee_record.id).delete()

        # Create upload log
        upload_log = create_test_fee_upload_log(self.school, self.admin)

        # Set student admission number
        self.student.admission_number = "STD123"
        self.student.save()

        # Create CSV content
        csv_content = [
            "Parent Name,Parent Email,Parent Phone,Student Name,Student Admission Number,"
            "Amount Due,Term,Year,Due Date (YYYY-MM-DD),Notes",
            f"{self.parent.user.get_full_name()},{self.parent.user.email},{self.parent.phone_number},"
            f"{self.student.full_name},{self.student.admission_number},"
            f"18000.00,term_1,{timezone.now().year},{date.today() + timedelta(days=30)},Test note",
        ]

        # Create file content
        file_content = "\n".join(csv_content)

        # Create a real file-like object
        mock_file = io.StringIO(file_content)
        mock_storage_open.return_value = mock_file

        # Create and attach dummy file
        dummy_file = SimpleUploadedFile(
            "test.csv", file_content.encode(), content_type="text/csv"
        )
        upload_log.file.save("test.csv", dummy_file)

        # Call task
        result = process_fee_upload(upload_log.id)

        # Get new record
        new_record = FeeRecord.objects.get(
            student=self.student,
            fee_structure__term="term_1",
            fee_structure__year=str(timezone.now().year),
        )

        # Verify
        self.assertEqual(result["successful"], 1)
        self.assertEqual(new_record.amount_owed, Decimal("18000.00"))

    @patch("skul_data.fee_management.utils.tasks.EmailMessage")
    @patch("skul_data.fee_management.utils.tasks.HTML")
    @patch("skul_data.fee_management.utils.tasks.render_to_string")
    def test_generate_fee_invoices(self, mock_render, mock_html, mock_email):
        """Test PDF invoice generation and email sending"""
        # Create invoice template
        template = create_test_fee_invoice_template(self.school)

        # Setup mocks
        mock_pdf = MagicMock()
        mock_html.return_value.write_pdf.return_value = mock_pdf
        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance
        mock_render.return_value = "Rendered content"

        # Ensure fee record is in correct state
        self.fee_record.payment_status = "unpaid"
        self.fee_record.save()

        # Call the task
        result = generate_fee_invoices([str(self.fee_record.id)], self.admin.id)

        # Verify results
        self.assertEqual(result["successful"], 1)
        self.assertEqual(result["failed"], 0)

        # Verify email was sent
        mock_email.assert_called_once()
        mock_email_instance.attach.assert_called_once()
        mock_email_instance.send.assert_called_once()

    @patch("skul_data.fee_management.utils.tasks.EmailMessage")
    @patch("skul_data.fee_management.utils.tasks.render_to_string")
    def test_check_overdue_fees(self, mock_render_to_string, mock_email_message):
        # Clear all records
        FeeRecord.objects.all().delete()
        FeeReminder.objects.all().delete()

        # Create test data with FUTURE date first (to avoid auto-overdue)
        future_date = date.today() + timedelta(days=2)
        record = FeeRecord.objects.create(
            student=self.student,
            parent=self.parent,
            fee_structure=self.fee_structure,
            amount_owed=Decimal("15000.00"),
            amount_paid=Decimal("0.00"),
            balance=Decimal("15000.00"),
            due_date=future_date,
            payment_status="unpaid",
        )

        # Manually set to past date while preserving initial state
        record.due_date = date.today() - timedelta(days=2)
        record.save(update_fields=["due_date"])  # Only update due_date

        # Verify initial state (should now be overdue due to model's save())
        self.assertTrue(record.is_overdue)
        self.assertEqual(record.payment_status, "overdue")

        # Setup parent email
        self.parent.user.email = "test@example.com"
        self.parent.user.save()

        # Mock email
        mock_email_instance = MagicMock()
        mock_email_message.return_value = mock_email_instance
        mock_email_instance.send.return_value = True

        # Mock template rendering
        mock_render_to_string.return_value = "Test content"

        # Run task
        with patch("django.utils.timezone.now", return_value=timezone.now()):
            result = check_overdue_fees()

        # Verify
        record.refresh_from_db()
        self.assertEqual(result["overdue_records_processed"], 1)
        self.assertTrue(record.is_overdue)
        self.assertEqual(record.payment_status, "overdue")
        self.assertEqual(FeeReminder.objects.count(), 1)


# python manage.py test skul_data.tests.fee_management_tests.test_fee_management_tasks
