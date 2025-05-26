from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.users.models import User


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    print(f"Signal triggered for {sender.__name__}")

    # Skip certain models
    if (
        sender.__module__ == "django.contrib.contenttypes.models"
        or sender.__name__ == "ActionLog"
    ):
        print(f"Skipping {sender.__name__} - excluded model")
        return

    # Try to get user from instance first, then from User class method
    user = getattr(instance, "_current_user", None)
    if not user:
        user = User.get_current_user()
        print(f"No _current_user on instance, got from User.get_current_user(): {user}")
    else:
        print(f"Got _current_user from instance: {user}")

    if not user:
        print("No user found, skipping action log")
        return

    # Check if user exists in database before creating log
    try:
        if user.pk and not User.objects.filter(pk=user.pk).exists():
            print(f"User {user.pk} doesn't exist in database, skipping")
            return  # Skip logging if user doesn't exist yet
    except Exception as e:
        print(f"Error checking user existence: {e}")
        return  # Skip on any database errors

    action = f"Created {sender.__name__}" if created else f"Updated {sender.__name__}"
    category = ActionCategory.CREATE if created else ActionCategory.UPDATE

    # Use transaction.on_commit to ensure the user is saved first
    from django.db import transaction

    def create_log():
        try:
            print(f"Creating action log: {action} by {user}")
            log_action(
                user=user,
                action=action,
                category=category,
                obj=instance,
                metadata={
                    "fields_changed": getattr(instance, "_changed_fields", None),
                    "new_values": {
                        field: getattr(instance, field)
                        for field in getattr(instance, "_changed_fields", [])
                    },
                },
            )
            print(f"Action log created successfully")
        except Exception as e:
            print(f"Failed to create action log: {e}")

    transaction.on_commit(create_log)


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    print(f"Delete signal triggered for {sender.__name__}")

    if (
        sender.__module__ == "django.contrib.contenttypes.models"
        or sender.__name__ == "ActionLog"
    ):
        print(f"Skipping {sender.__name__} - excluded model")
        return

    # Try to get user from instance first, then from User class method
    user = getattr(instance, "_current_user", None)
    if not user:
        user = User.get_current_user()
        print(f"No _current_user on instance, got from User.get_current_user(): {user}")
    else:
        print(f"Got _current_user from instance: {user}")

    if not user:
        print("No user found, skipping delete action log")
        return

    try:
        print(f"Creating delete action log: Deleted {sender.__name__} by {user}")
        log_action(
            user=user,
            action=f"Deleted {sender.__name__}",
            category=ActionCategory.DELETE,
            obj=instance,
        )
        print(f"Delete action log created successfully")
    except Exception as e:
        print(f"Failed to create delete action log: {e}")
