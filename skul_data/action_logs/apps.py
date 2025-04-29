from django.apps import AppConfig


class ActionLogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.action_logs"
    label = "action_logs"

    def ready(self):
        import skul_data.action_logs.signals
