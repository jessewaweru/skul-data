# users/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.users.models.school_admin import AdministratorProfile


@receiver(post_save, sender=AdministratorProfile)
def log_administrator_changes(sender, instance, created, **kwargs):
    """Log creation and updates of AdministratorProfile"""
    user = getattr(instance, "_current_user", None)
    if not user:
        from skul_data.users.models.base_user import User

        user = User.get_current_user()

    if not user:
        return

    def create_log():
        try:
            if created:
                log_action(
                    user=user,
                    action=f"Created administrator profile for {instance.user.get_full_name()}",
                    category=ActionCategory.CREATE,
                    obj=instance,
                    metadata={
                        "action_type": "ADMIN_PROFILE_CREATE",  # Add this key
                        "position": instance.position,
                        "access_level": instance.access_level,
                        "permissions": instance.permissions_granted,
                        "school_id": instance.school.id if instance.school else None,
                    },
                )
            else:
                # Log updates to important fields
                changed_fields = getattr(instance, "_changed_fields", [])
                if changed_fields:
                    log_action(
                        user=user,
                        action=f"Updated administrator profile for {instance.user.get_full_name()}",
                        category=ActionCategory.UPDATE,
                        obj=instance,
                        metadata={
                            "action_type": "ADMIN_PROFILE_UPDATE",  # Add this key
                            "changed_fields": changed_fields,
                            "position": instance.position,
                            "access_level": instance.access_level,
                            "permissions": instance.permissions_granted,
                            "school_id": (
                                instance.school.id if instance.school else None
                            ),
                        },
                    )
        except Exception:
            pass  # Silently fail logging

    # For tests, execute immediately without transaction.on_commit
    from skul_data.action_logs.utils.action_log import _TEST_MODE

    if _TEST_MODE:
        create_log()
    else:
        transaction.on_commit(create_log)


@receiver(post_delete, sender=AdministratorProfile)
def log_administrator_deletion(sender, instance, **kwargs):
    """Log deletion of AdministratorProfile"""
    user = getattr(instance, "_current_user", None)
    if not user:
        from skul_data.users.models.base_user import User

        user = User.get_current_user()

    if not user:
        return

    log_action(
        user=user,
        action=f"Deleted administrator profile for {instance.user.get_full_name()}",
        category=ActionCategory.DELETE,
        obj=instance,
        metadata={
            "action_type": "ADMIN_PROFILE_DELETE",  # Add this key
            "position": instance.position,
            "access_level": instance.access_level,
            "school_id": instance.school.id if instance.school else None,
        },
    )
