# skul_data/fee_management/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from skul_data.fee_management.views.fee_management import (
    FeeStructureViewSet,
    FeeRecordViewSet,
    FeePaymentViewSet,
    FeeUploadLogViewSet,
    FeeInvoiceTemplateViewSet,
    FeeReminderViewSet,
    FeeCSVTemplateViewSet,
    ParentFeeViewSet,
)

router = DefaultRouter()
router.register(r"fee-structures", FeeStructureViewSet, basename="fee-structure")
router.register(r"fee-records", FeeRecordViewSet, basename="fee-record")
router.register(r"fee-payments", FeePaymentViewSet, basename="fee-payment")
router.register(r"fee-uploads", FeeUploadLogViewSet, basename="fee-upload")
router.register(
    r"fee-invoice-templates", FeeInvoiceTemplateViewSet, basename="fee-invoice-template"
)
router.register(r"fee-reminders", FeeReminderViewSet, basename="fee-reminder")
router.register(
    r"fee-csv-templates", FeeCSVTemplateViewSet, basename="fee-csv-template"
)
router.register(r"parent-fees", ParentFeeViewSet, basename="parent-fee")

urlpatterns = [
    path("", include(router.urls)),
]
