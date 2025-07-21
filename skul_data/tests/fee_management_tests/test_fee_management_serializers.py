from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from skul_data.tests.fee_management_tests.test_helpers import (
    create_test_school_with_fee_data,
    create_test_fee_structure,
    create_test_fee_record,
    create_test_parent,
    create_test_class,
    create_test_fee_payment,
    create_test_fee_upload_log,
)
from skul_data.fee_management.serializers.fee_management import (
    FeeStructureSerializer,
    FeeRecordSerializer,
    FeePaymentSerializer,
    FeeUploadLogSerializer,
    FeePaymentConfirmationSerializer,
    FeeSummarySerializer,
)


class FeeStructureSerializerTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.school_class = self.test_data["class"]
        self.admin = self.test_data["admin"]

    def test_serialize_fee_structure(self):
        fee_structure = create_test_fee_structure(self.school, self.school_class)
        serializer = FeeStructureSerializer(fee_structure)

        self.assertEqual(serializer.data["school_class"]["id"], self.school_class.id)
        self.assertEqual(serializer.data["term"], fee_structure.term)
        self.assertEqual(serializer.data["amount"], str(fee_structure.amount))
        self.assertTrue(serializer.data["is_active"])

    def test_create_fee_structure(self):
        data = {
            "school_class_id": self.school_class.id,
            "term": "term_2",
            "year": str(timezone.now().year + 1),
            "amount": "20000.00",
            "due_date": (timezone.now().date() + timedelta(days=60)).isoformat(),
        }

        # Create a mock request object with the school context
        class MockRequest:
            def __init__(self, user):
                self.user = user

        mock_request = MockRequest(self.admin)

        serializer = FeeStructureSerializer(
            data=data, context={"request": mock_request}
        )

        # Print errors if validation fails for debugging
        if not serializer.is_valid():
            print("FeeStructure validation errors:", serializer.errors)

        self.assertTrue(serializer.is_valid())

        # Set the school before saving
        fee_structure = serializer.save(school=self.school)

        self.assertEqual(fee_structure.school, self.school)
        self.assertEqual(fee_structure.school_class, self.school_class)
        self.assertEqual(fee_structure.term, "term_2")
        self.assertEqual(fee_structure.amount, Decimal("20000.00"))

    def test_validate_amount(self):
        data = {
            "school_class_id": self.school_class.id,
            "term": "term_2",
            "year": str(timezone.now().year + 1),
            "amount": "-100.00",
            "due_date": (timezone.now().date() + timedelta(days=60)).isoformat(),
        }

        serializer = FeeStructureSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("amount", serializer.errors)

    def test_validate_due_date(self):
        data = {
            "school_class_id": self.school_class.id,
            "term": "term_2",
            "year": str(timezone.now().year + 1),
            "amount": "20000.00",
            "due_date": (timezone.now().date() - timedelta(days=1)).isoformat(),
        }

        serializer = FeeStructureSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("due_date", serializer.errors)


class FeeRecordSerializerTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.student = self.test_data["student"]
        self.parent = self.test_data["parent"]
        self.fee_structure = self.test_data["fee_structure"]
        self.school = self.test_data["school"]
        self.admin = self.test_data["admin"]

    def test_serialize_fee_record(self):
        # Use the existing fee record from test data or create a new one with different parameters
        existing_fee_record = self.test_data.get("fee_record")

        if existing_fee_record:
            # Update the existing fee record for this test
            existing_fee_record.amount_paid = Decimal("5000.00")
            existing_fee_record.save()
            fee_record = existing_fee_record
        else:
            # Create fee record explicitly for this test
            fee_record = create_test_fee_record(
                self.student,
                self.parent,
                self.fee_structure,
                amount_paid=Decimal("5000.00"),
            )

        serializer = FeeRecordSerializer(fee_record)

        self.assertEqual(serializer.data["student"]["id"], self.student.id)
        self.assertEqual(serializer.data["parent"]["id"], self.parent.id)
        self.assertEqual(serializer.data["fee_structure"]["id"], self.fee_structure.id)
        self.assertEqual(serializer.data["amount_owed"], str(fee_record.amount_owed))
        self.assertEqual(serializer.data["amount_paid"], str(fee_record.amount_paid))
        self.assertEqual(serializer.data["balance"], str(fee_record.balance))
        self.assertEqual(serializer.data["payment_status"], fee_record.payment_status)

    def test_create_fee_record(self):
        # Create a new fee structure for this test to avoid duplicates
        new_fee_structure = create_test_fee_structure(
            self.school,
            self.test_data["class"],
            term="term_2",  # Different term
            year=str(timezone.now().year + 1),  # Different year
        )

        data = {
            "student_id": self.student.id,
            "parent_id": self.parent.id,
            "fee_structure_id": new_fee_structure.id,  # Use new fee structure
            "amount_owed": "18000.00",
            "due_date": (timezone.now().date() + timedelta(days=30)).isoformat(),
        }

        # Create a mock request object
        class MockRequest:
            def __init__(self, user):
                self.user = user

        mock_request = MockRequest(self.admin)

        serializer = FeeRecordSerializer(data=data, context={"request": mock_request})

        # Print errors if validation fails for debugging
        if not serializer.is_valid():
            print("FeeRecord validation errors:", serializer.errors)
            # Also print the student's class information for debugging
            print(
                f"Student class: {getattr(self.student, 'student_class', None) or getattr(self.student, 'school_class', None)}"
            )
            print(f"Fee structure class: {new_fee_structure.school_class}")

        self.assertTrue(serializer.is_valid())
        fee_record = serializer.save()

        self.assertEqual(fee_record.student, self.student)
        self.assertEqual(fee_record.parent, self.parent)
        self.assertEqual(fee_record.fee_structure, new_fee_structure)
        self.assertEqual(fee_record.amount_owed, Decimal("18000.00"))

    def test_validate_student_parent_relationship(self):
        # Create another parent not related to the student
        other_parent = create_test_parent(self.school)

        data = {
            "student_id": self.student.id,
            "parent_id": other_parent.id,
            "fee_structure_id": self.fee_structure.id,
            "amount_owed": "18000.00",
            "due_date": (timezone.now().date() + timedelta(days=30)).isoformat(),
        }

        serializer = FeeRecordSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("student_id", serializer.errors)

    def test_validate_student_class_relationship(self):
        # Create another class
        other_class = create_test_class(self.school, name="Class 2")

        # Create fee structure for the other class
        other_fee_structure = create_test_fee_structure(
            self.school, other_class, term="term_2"
        )

        data = {
            "student_id": self.student.id,
            "parent_id": self.parent.id,
            "fee_structure_id": other_fee_structure.id,
            "amount_owed": "18000.00",
            "due_date": (timezone.now().date() + timedelta(days=30)).isoformat(),
        }

        serializer = FeeRecordSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("student_id", serializer.errors)


class FeePaymentSerializerTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.fee_record = self.test_data["fee_record"]

    def test_serialize_fee_payment(self):
        fee_payment = create_test_fee_payment(self.fee_record)
        serializer = FeePaymentSerializer(fee_payment)

        self.assertEqual(serializer.data["fee_record"], self.fee_record.id)
        self.assertEqual(serializer.data["amount"], str(fee_payment.amount))
        self.assertEqual(serializer.data["payment_method"], fee_payment.payment_method)
        self.assertEqual(
            serializer.data["transaction_reference"], fee_payment.transaction_reference
        )
        self.assertEqual(serializer.data["is_confirmed"], fee_payment.is_confirmed)

    def test_create_fee_payment(self):
        data = {
            "fee_record": self.fee_record.id,  # Add this line
            "amount": "7500.00",
            "payment_method": "bank",
            "transaction_reference": "BANK12345",
            "receipt_number": "RCPT67890",
            "payment_date": timezone.now().date().isoformat(),
            "notes": "Test payment",
        }

        serializer = FeePaymentSerializer(data=data)

        # Print errors if validation fails for debugging
        if not serializer.is_valid():
            print("FeePayment validation errors:", serializer.errors)

        self.assertTrue(serializer.is_valid())
        fee_payment = serializer.save()  # Remove fee_record parameter from save()

        self.assertEqual(fee_payment.fee_record, self.fee_record)
        self.assertEqual(fee_payment.amount, Decimal("7500.00"))
        self.assertEqual(fee_payment.payment_method, "bank")
        self.assertFalse(fee_payment.is_confirmed)  # Default should be False

    def test_validate_amount(self):
        data = {
            "amount": "0.00",
            "payment_method": "bank",
            "transaction_reference": "BANK12345",
        }

        serializer = FeePaymentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("amount", serializer.errors)


class FeeUploadLogSerializerTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.school = self.test_data["school"]
        self.admin = self.test_data["admin"]

    def test_serialize_fee_upload_log(self):
        upload_log = create_test_fee_upload_log(self.school, self.admin)
        serializer = FeeUploadLogSerializer(upload_log)

        self.assertEqual(serializer.data["school"], self.school.id)
        self.assertEqual(serializer.data["uploaded_by"], self.admin.id)
        self.assertEqual(serializer.data["term"], upload_log.term)
        self.assertEqual(serializer.data["status"], upload_log.status)


class FeePaymentConfirmationSerializerTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()

    def test_serializer_validation(self):
        # Create a simple test image file
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io

        # Create a simple image
        img = Image.new("RGB", (100, 100), color="red")
        img_file = io.BytesIO()
        img.save(img_file, format="JPEG")
        img_file.seek(0)

        test_image = SimpleUploadedFile(
            name="test_receipt.jpg", content=img_file.read(), content_type="image/jpeg"
        )

        data = {
            "amount": "5000.00",
            "payment_method": "mpesa",
            "transaction_reference": "MPESA12345",
            "receipt_number": "RCPT12345",
            "payment_date": timezone.now().date().isoformat(),
            "receipt_image": test_image,
        }

        serializer = FeePaymentConfirmationSerializer(data=data)

        # Print errors if validation fails for debugging
        if not serializer.is_valid():
            print("FeePaymentConfirmation validation errors:", serializer.errors)

        self.assertTrue(serializer.is_valid())

    def test_invalid_amount(self):
        data = {
            "amount": "0.00",
            "payment_method": "mpesa",
            "transaction_reference": "MPESA12345",
        }

        serializer = FeePaymentConfirmationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("amount", serializer.errors)


class FeeSummarySerializerTest(TestCase):
    def test_serializer(self):
        data = {
            "term": "term_1",
            "year": "2023",
            "school_class": {"id": 1, "name": "Class 1"},
            "total_students": 30,
            "total_expected": "450000.00",
            "total_paid": "300000.00",
            "total_balance": "150000.00",
            "paid_percentage": "66.67",
            "unpaid_count": 5,
            "partially_paid_count": 10,
            "fully_paid_count": 15,
            "overdue_count": 3,
        }

        serializer = FeeSummarySerializer(data=data)

        # Print errors if validation fails for debugging
        if not serializer.is_valid():
            print("FeeSummary validation errors:", serializer.errors)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["term"], "term_1")
        self.assertEqual(
            serializer.validated_data["total_expected"], Decimal("450000.00")
        )


# python manage.py test skul_data.tests.fee_management_tests.test_fee_management_serializers
