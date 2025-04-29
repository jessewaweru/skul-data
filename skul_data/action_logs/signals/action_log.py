from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.action_logs.utils.action_log import log_action


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    if (
        sender.__module__ == "django.contrib.contenttypes.models"
        or sender.__name__ == "ActionLog"
    ):
        return

    user = getattr(instance, "_current_user", None)
    if not user:
        return

    action = f"Created {sender.__name__}" if created else f"Updated {sender.__name__}"
    category = (
        ActionLog.ActionCategory.CREATE if created else ActionLog.ActionCategory.UPDATE
    )

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


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    if (
        sender.__module__ == "django.contrib.contenttypes.models"
        or sender.__name__ == "ActionLog"
    ):
        return

    user = getattr(instance, "_current_user", None)
    if not user:
        return

    log_action(
        user=user,
        action=f"Deleted {sender.__name__}",
        category=ActionLog.ActionCategory.DELETE,
        obj=instance,
    )
