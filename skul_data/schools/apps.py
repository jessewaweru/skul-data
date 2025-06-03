from django.apps import AppConfig


class SchoolsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.schools"
    label = "schools"

    def ready(self):
        from skul_data.schools.signals import schoolclass
