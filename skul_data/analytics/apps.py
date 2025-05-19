from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.analytics"
    label = "analytics"

    # def ready(self):
    #     import skul_data.analytics.signals
    def ready(self):
        # This ensures tasks are imported when Django starts
        from skul_data.analytics.utils import tasks
