from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.users"
    label = "users"

    def ready(self):
        # Import models first
        from skul_data.users.models.base_user import User
        from skul_data.users.signals import teacher
        from skul_data.users.signals import role
