# skul_data/fee_management/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from skul_data.fee_management.models.fee_management import FeeRecord, FeePayment


@receiver(pre_save, sender=FeeRecord)
def update_fee_record_status(sender, instance, **kwargs):
    """Update payment status and overdue flag before saving FeeRecord"""
    # Calculate balance
    instance.balance = instance.amount_owed - instance.amount_paid

    # Update payment status
    if instance.amount_paid <= 0:
        instance.payment_status = FeeRecord.PAYMENT_STATUS.unpaid
    elif instance.balance <= 0:
        instance.payment_status = FeeRecord.PAYMENT_STATUS.paid
    else:
        instance.payment_status = FeeRecord.PAYMENT_STATUS.partial

    # Check if overdue
    instance.is_overdue = (
        instance.balance > 0 and timezone.now().date() > instance.due_date
    )
    if (
        instance.is_overdue
        and instance.payment_status != FeeRecord.PAYMENT_STATUS.overdue
    ):
        instance.payment_status = FeeRecord.PAYMENT_STATUS.overdue


@receiver(post_save, sender=FeePayment)
def update_fee_record_on_payment(sender, instance, created, **kwargs):
    """Update the related FeeRecord when a payment is made"""
    if created:
        fee_record = instance.fee_record
        fee_record.amount_paid += instance.amount
        fee_record.last_payment_date = instance.payment_date
        fee_record.save()
