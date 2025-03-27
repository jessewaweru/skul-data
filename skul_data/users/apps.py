from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.users"
    label = "users"

    def ready(self):
        # Import models to ensure they're registered
        from .models.base_user import User
