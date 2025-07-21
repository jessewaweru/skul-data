from django.apps import AppConfig


class FeeManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.fee_management"
    label = "fee_management"

    def ready(self):
        # Import models first
        from skul_data.fee_management.signals import fee_management
