import io
import csv
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from skul_data.tests.fee_management_tests.test_helpers import (
    create_test_school_with_fee_data,
    create_test_fee_structure,
    create_test_fee_record,
    create_test_fee_payment,
    create_test_fee_upload_log,
    create_test_class,
    create_test_school_with_fee_data_and_payment,
)
from skul_data.users.models import User
import random
from skul_data.fee_management.models.fee_management import FeeStructure, FeeRecord
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from io import BytesIO


class FeeStructureViewSetTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.admin = self.test_data["admin"]
        self.school_class = self.test_data["class"]

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.url = reverse("fee-structure-list")

    def test_list_fee_structures(self):
        # Clear any existing fee structures
        FeeStructure.objects.all().delete()

        # Now create just one
        fee_structure = create_test_fee_structure(self.school, self.school_class)

        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_fee_structure(self):
        data = {
            "school_class_id": self.school_class.id,
            "term": "term_2",
            "year": str(timezone.now().year + 1),
            "amount": "20000.00",
            "due_date": (timezone.now().date() + timedelta(days=60)).isoformat(),
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["term"], "term_2")
        self.assertEqual(response.data["amount"], "20000.00")

    # def test_filter_by_class(self):
    #     # Create test data
    #     fee_structure1 = create_test_fee_structure(self.school, self.school_class)

    #     # Create another class and fee structure
    #     other_class = create_test_class(self.school, name="Class 2")
    #     fee_structure2 = create_test_fee_structure(
    #         self.school, other_class, term="term_2"
    #     )

    #     # Filter by class
    #     response = self.client.get(self.url, {"class_id": self.school_class.id})

    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(len(response.data["results"]), 1)
    #     self.assertEqual(response.data["results"][0]["id"], fee_structure1.id)

    def test_filter_by_class(self):
        # Clear existing
        FeeStructure.objects.all().delete()

        # Create test data
        fee_structure1 = create_test_fee_structure(self.school, self.school_class)

        # Create another class and fee structure
        other_class = create_test_class(self.school, name="Class 2")
        fee_structure2 = create_test_fee_structure(
            self.school, other_class, term="term_2"
        )

        response = self.client.get(self.url, {"class_id": self.school_class.id})
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_term(self):
        # Clear existing
        FeeStructure.objects.all().delete()

        # Create test data with specific terms
        fee_structure1 = create_test_fee_structure(
            self.school, self.school_class, term="term_1"
        )
        fee_structure2 = create_test_fee_structure(
            self.school, self.school_class, term="term_2"
        )

        response = self.client.get(self.url, {"term": "term_1"})
        self.assertEqual(len(response.data["results"]), 1)


class FeeRecordViewSetTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.admin = self.test_data["admin"]
        self.student = self.test_data["student"]
        self.parent = self.test_data["parent"]
        self.fee_structure = self.test_data["fee_structure"]
        self.fee_record = self.test_data["fee_record"]

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.url = reverse("fee-record-list")

    def test_list_fee_records(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.fee_record.id)

    def test_filter_by_student(self):
        response = self.client.get(self.url, {"student_id": self.student.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.fee_record.id)

    def test_filter_by_parent(self):
        response = self.client.get(self.url, {"parent_id": self.parent.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.fee_record.id)

    def test_filter_by_class(self):
        response = self.client.get(
            self.url, {"class_id": self.fee_structure.school_class.id}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.fee_record.id)

    def test_filter_by_status(self):
        # Clear existing
        FeeRecord.objects.all().delete()

        # Create a paid record
        paid_record = create_test_fee_record(
            self.student,
            self.parent,
            self.fee_structure,
            amount_paid=self.fee_structure.amount,
        )

        response = self.client.get(self.url, {"status": "paid"})
        self.assertEqual(len(response.data["results"]), 1)

    def test_add_payment(self):
        add_payment_url = reverse(
            "fee-record-add-payment", kwargs={"pk": self.fee_record.id}
        )

        data = {
            "fee_record": self.fee_record.id,  # Add this required field
            "amount": "5000.00",
            "payment_method": "mpesa",
            "transaction_reference": "MPESA12345",
            "payment_date": timezone.now().date().isoformat(),
            "receipt_number": "RCPT12345",
            "confirmed_by": self.admin.id if hasattr(self, "admin") else None,
            "is_confirmed": True,
        }

        print("Sending data:", data)  # Debug print
        response = self.client.post(add_payment_url, data, format="json")
        print("Response data:", response.data)  # Debug print
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_summary_endpoint(self):
        # Ensure the user has a school set
        self.admin.school_admin_profile = self.test_data["school_admin_profile"]
        self.admin.save()

        # Ensure the fee structure has term_1
        self.fee_record.fee_structure.term = "term_1"
        self.fee_record.fee_structure.save()

        summary_url = reverse("fee-record-summary")

        response = self.client.get(summary_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["term"], "term_1")
        self.assertEqual(response.data[0]["total_expected"], "15000.00")


class FeePaymentViewSetTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data_and_payment()
        self.admin = self.test_data["admin"]
        self.fee_record = self.test_data["fee_record"]
        self.fee_payment = self.test_data["fee_payment"]

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.url = reverse("fee-payment-list")

    def test_list_fee_payments(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.fee_payment.id)

    def test_filter_by_fee_record(self):
        response = self.client.get(self.url, {"fee_record_id": self.fee_record.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.fee_payment.id)

    def test_confirm_payment(self):
        # Create an unconfirmed payment
        payment = create_test_fee_payment(self.fee_record, is_confirmed=False)

        confirm_url = reverse("fee-payment-confirm", kwargs={"pk": payment.id})

        response = self.client.post(confirm_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh payment
        payment.refresh_from_db()
        self.assertTrue(payment.is_confirmed)
        self.assertEqual(payment.confirmed_by, self.admin)


class FeeUploadLogViewSetTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.admin = self.test_data["admin"]
        self.school_class = self.test_data["class"]

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.url = reverse("fee-upload-list")

    def test_list_upload_logs(self):
        # Create test data
        upload_log = create_test_fee_upload_log(self.school, self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], upload_log.id)

    def test_create_upload_log(self):
        # Create a test CSV file
        csv_file = io.StringIO()
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "Parent Name",
                "Parent Email",
                "Parent Phone",
                "Student Name",
                "Student Admission Number",
                "Amount Due",
                "Term",
                "Year",
                "Due Date (YYYY-MM-DD)",
                "Notes",
            ]
        )
        writer.writerow(
            [
                "Test Parent",
                "parent@test.com",
                "+254700000000",
                "Test Student",
                "TEST-2023-001",
                "15000.00",
                "term_1",
                "2023",
                "2023-06-30",
                "Test note",
            ]
        )
        csv_file.seek(0)

        data = {
            "file": csv_file,
            "school_class_id": self.school_class.id,
            "term": "term_1",
            "year": "2023",
        }

        response = self.client.post(self.url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")


class FeeCSVTemplateViewSetTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.admin = self.test_data["admin"]
        self.school_class = self.test_data["class"]

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.url = reverse("fee-csv-template-download")

    def test_download_csv_template(self):
        data = {
            "school_class_id": self.school_class.id,
            "term": "term_1",
            "year": "2023",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(
            f'attachment; filename="fee_template_{self.school_class.name}_term_1_2023.csv"',
            response["Content-Disposition"],
        )

        # Read the CSV content
        content = response.content.decode("utf-8")
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        # Check header row
        self.assertEqual(
            rows[0],
            [
                "Parent Name",
                "Parent Email",
                "Parent Phone",
                "Student Name",
                "Student Admission Number",
                "Amount Due",
                "Term",
                "Year",
                "Due Date (YYYY-MM-DD)",
                "Notes",
            ],
        )

        # Check at least one data row exists
        self.assertGreater(len(rows), 1)

    def test_sample_endpoint(self):
        sample_url = reverse("fee-csv-template-sample")

        response = self.client.get(sample_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("headers", response.data)
        self.assertIn("sample_rows", response.data)


class ParentFeeViewSetTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.parent_user = self.test_data["parent"].user
        self.fee_record = self.test_data["fee_record"]

        self.client = APIClient()
        self.client.force_authenticate(user=self.parent_user)

        self.url = reverse("parent-fee-records")

    def test_list_records(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.fee_record.id)

    def test_current_records(self):
        # Set school's current term/year to match our test data
        school = self.test_data["school"]
        school.current_term = self.fee_record.fee_structure.term
        school.current_school_year = self.fee_record.fee_structure.year
        school.save()

        current_url = reverse("parent-fee-current")
        response = self.client.get(current_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_confirm_payment(self):
        confirm_url = reverse(
            "parent-fee-confirm-payment", kwargs={"pk": self.fee_record.id}
        )

        # Create a valid mock image file
        image = Image.new("RGB", (100, 100), color="red")
        image_file = BytesIO()
        image.save(image_file, "jpeg")
        image_file.seek(0)

        mock_image = SimpleUploadedFile(
            "receipt.jpg", image_file.read(), content_type="image/jpeg"
        )

        data = {
            "amount": "5000.00",
            "payment_method": "mpesa",
            "transaction_reference": f"MPESA{random.randint(100000, 999999)}",
            "receipt_number": f"RCPT{random.randint(10000, 99999)}",
            "payment_date": timezone.now().date().isoformat(),
            "receipt_image": mock_image,
            "notes": "",  # Add if required
            "confirmed_by": "",  # Empty string instead of None
            "is_confirmed": "false",  # String for form data
        }

        print("Sending data:", {k: v for k, v in data.items() if k != "receipt_image"})
        response = self.client.post(confirm_url, data)
        print("Response data:", response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# python manage.py test skul_data.tests.fee_management_tests.test_fee_management_views
