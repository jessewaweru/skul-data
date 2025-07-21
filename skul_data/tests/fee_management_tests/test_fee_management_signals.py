from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from skul_data.tests.fee_management_tests.test_helpers import (
    create_test_school_with_fee_data,
    create_test_fee_payment,
)
from skul_data.fee_management.models.fee_management import FeeRecord
from skul_data.fee_management.signals.fee_management import (
    update_fee_record_status,
)


class FeeManagementSignalsTest(TestCase):
    def setUp(self):
        self.test_data = create_test_school_with_fee_data()
        self.fee_record = self.test_data["fee_record"]

    def test_update_fee_record_status_pre_save(self):
        """Test the pre_save signal that updates fee record status"""
        # Initial state
        self.assertEqual(self.fee_record.payment_status, "unpaid")
        self.assertEqual(self.fee_record.balance, self.fee_record.amount_owed)

        # Test partial payment
        self.fee_record.amount_paid = Decimal("5000.00")
        update_fee_record_status(FeeRecord, self.fee_record)

        self.assertEqual(self.fee_record.payment_status, "partial")
        self.assertEqual(self.fee_record.balance, Decimal("10000.00"))

        # Test fully paid
        self.fee_record.amount_paid = self.fee_record.amount_owed
        update_fee_record_status(FeeRecord, self.fee_record)

        self.assertEqual(self.fee_record.payment_status, "paid")
        self.assertEqual(self.fee_record.balance, Decimal("0.00"))

        # Test overdue status
        self.fee_record.amount_paid = Decimal("5000.00")
        self.fee_record.due_date = timezone.now().date() - timedelta(days=1)
        update_fee_record_status(FeeRecord, self.fee_record)

        self.assertEqual(self.fee_record.payment_status, "overdue")
        self.assertTrue(self.fee_record.is_overdue)

    def test_update_fee_record_on_payment_post_save(self):
        """Test the post_save signal for FeePayment"""
        initial_amount_paid = self.fee_record.amount_paid
        initial_last_payment = self.fee_record.last_payment_date

        # Create a new payment
        payment = create_test_fee_payment(
            self.fee_record, amount=Decimal("3000.00"), payment_date=date.today()
        )

        # Signal should have updated the fee record
        self.fee_record.refresh_from_db()

        self.assertEqual(
            self.fee_record.amount_paid, initial_amount_paid + payment.amount
        )
        self.assertEqual(self.fee_record.last_payment_date, payment.payment_date)
        self.assertEqual(self.fee_record.payment_status, "partial")


# python manage.py test skul_data.tests.fee_management_tests.test_fee_management_signals
