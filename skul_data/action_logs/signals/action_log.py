from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.users.models import User
from skul_data.documents.models.document import DocumentShareLink


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    # Skip certain models
    if (
        sender.__module__ == "django.contrib.contenttypes.models"
        or sender.__name__ == "ActionLog"
    ):
        return

    # Try to get user from instance first, then from User class method
    user = getattr(instance, "_current_user", None)
    if not user:
        user = User.get_current_user()

    if not user:
        return

    # Check if user exists in database before creating log
    try:
        if user.pk and not User.objects.filter(pk=user.pk).exists():
            return  # Skip logging if user doesn't exist yet
    except Exception:
        return  # Skip on any database errors

    action = f"Created {sender.__name__}" if created else f"Updated {sender.__name__}"
    category = ActionCategory.CREATE if created else ActionCategory.UPDATE

    # Use transaction.on_commit to ensure the user is saved first
    from django.db import transaction

    def create_log():
        try:
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
        except Exception:
            pass

    transaction.on_commit(create_log)


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    if (
        sender.__module__ == "django.contrib.contenttypes.models"
        or sender.__name__ == "ActionLog"
    ):
        return

    # Try to get user from instance first, then from User class method
    user = getattr(instance, "_current_user", None)
    if not user:
        user = User.get_current_user()

    if not user:
        return

    try:
        log_action(
            user=user,
            action=f"Deleted {sender.__name__}",
            category=ActionCategory.DELETE,
            obj=instance,
        )
    except Exception:
        pass


@receiver(post_save, sender=DocumentShareLink)
def log_share_link_creation(sender, instance, created, **kwargs):
    """Signal handler specifically for DocumentShareLink creation and updates"""
    try:
        # Get user from instance or fallback methods
        user = getattr(instance, "_current_user", None)
        if not user:
            user = instance.created_by  # Use the created_by field as fallback

        if not user:
            return

        # Check if user exists in database
        if user.pk and not User.objects.filter(pk=user.pk).exists():
            return

        if created:
            # Log share link creation
            expires_at = (
                instance.expires_at.isoformat() if instance.expires_at else None
            )

            log_action(
                user=user,
                action=f"Created share link for document: {instance.document.title}",
                category=ActionCategory.SHARE,
                obj=instance,
                metadata={
                    "document_id": instance.document.id,
                    "expires_at": expires_at,
                    "has_password": bool(instance.password),
                    "download_limit": instance.download_limit,
                },
            )
        else:
            # Log share link updates (like download count increments)
            changed_fields = getattr(instance, "_changed_fields", [])

            # Check if download_count was incremented
            if "download_count" in changed_fields or hasattr(
                instance, "_download_increment"
            ):
                log_action(
                    user=user,
                    action=f"Document downloaded via share link: {instance.document.title}",
                    category=ActionCategory.DOWNLOAD,
                    obj=instance,
                    metadata={
                        "document_id": instance.document.id,
                        "download_count": instance.download_count,
                        "via_share_link": True,
                    },
                )
            else:
                # General update
                log_action(
                    user=user,
                    action=f"Updated share link for document: {instance.document.title}",
                    category=ActionCategory.UPDATE,
                    obj=instance,
                    metadata={
                        "document_id": instance.document.id,
                        "fields_changed": changed_fields,
                        "download_count": instance.download_count,
                    },
                )

    except Exception:
        pass
