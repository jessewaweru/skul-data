from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.reports"
    label = "reports"

    def ready(self):
        # This ensures tasks are imported when Django starts
        from skul_data.reports.utils import tasks  # noqa
