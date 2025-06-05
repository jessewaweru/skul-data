from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.users.models import User
from skul_data.documents.models.document import DocumentShareLink
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
import logging


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    """Enhanced signal handler with better error handling and content type validation"""

    # Skip certain models - be more specific about what to skip
    skip_models = {
        "ActionLog",  # Our own model
        "ContentType",  # Django's content type model
        "Session",  # User sessions
        "LogEntry",  # Admin log entries
        "Migration",  # Django migrations
    }

    # Skip if sender is in our skip list
    if (
        sender.__module__ == "django.contrib.contenttypes.models"
        or sender.__name__ in skip_models
    ):
        return

    # Try to get user from instance first, then from User class method
    user = getattr(instance, "_current_user", None)
    if not user:
        user = User.get_current_user()

    if not user:
        return

    # Robust user validation
    try:
        if user.pk and not User.objects.filter(pk=user.pk).exists():
            return  # Skip logging if user doesn't exist yet
    except Exception:
        return  # Skip on any database errors

    # Validate that content type exists before proceeding
    try:
        content_type = ContentType.objects.get_for_model(sender)
        if not content_type:
            return
    except Exception:
        # If we can't get a content type, skip logging
        return

    action = f"Created {sender.__name__}" if created else f"Updated {sender.__name__}"
    category = ActionCategory.CREATE if created else ActionCategory.UPDATE

    def create_log():
        try:
            # Double-check content type still exists at log creation time
            ContentType.objects.get_for_model(sender)

            log_action(
                user=user,
                action=action,
                category=category,
                obj=instance,
                metadata={
                    "fields_changed": getattr(instance, "_changed_fields", None),
                    "new_values": (
                        {
                            field: getattr(instance, field, None)
                            for field in getattr(instance, "_changed_fields", [])
                        }
                        if getattr(instance, "_changed_fields", None)
                        else {}
                    ),
                },
            )
        except Exception as e:
            # Silently fail but optionally log the error
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Failed to create action log: {str(e)}")

    # Use transaction.on_commit to ensure the user and content type are saved first
    try:
        transaction.on_commit(create_log)
    except Exception:
        # If transaction handling fails, try immediate execution
        create_log()


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    """Enhanced delete signal handler"""

    skip_models = {"ActionLog", "ContentType", "Session", "LogEntry", "Migration"}

    if (
        sender.__module__ == "django.contrib.contenttypes.models"
        or sender.__name__ in skip_models
    ):
        return

    user = getattr(instance, "_current_user", None)
    if not user:
        user = User.get_current_user()

    if not user:
        return

    try:
        metadata = {"deleted_id": instance.pk}

        # Model-specific metadata extraction
        if sender.__name__ == "Parent":
            if hasattr(instance, "user") and instance.user:
                metadata["name"] = (
                    f"{instance.user.first_name} {instance.user.last_name}".strip()
                )
                metadata["email"] = instance.user.email
            metadata["phone_number"] = getattr(instance, "phone_number", None)
            metadata["status"] = getattr(instance, "status", None)
        elif sender.__name__ == "Student":
            metadata["name"] = f"{instance.first_name} {instance.last_name}".strip()
            metadata["student_id"] = getattr(instance, "student_id", None)
        # Add other model-specific cases as needed
        else:
            # Generic fallback
            if hasattr(instance, "name"):
                metadata["name"] = instance.name
            if hasattr(instance, "title"):
                metadata["title"] = instance.title

        log_action(
            user=user,
            action=f"Deleted {sender.__name__}",
            category=ActionCategory.DELETE,
            obj=instance,
            metadata=metadata,
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Failed to log deletion: {str(e)}")


@receiver(post_save, sender=DocumentShareLink)
def log_share_link_creation(sender, instance, created, **kwargs):
    """Signal handler specifically for DocumentShareLink creation and updates"""

    try:
        # Validate content type exists for DocumentShareLink
        ContentType.objects.get_for_model(DocumentShareLink)

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

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Failed to log share link action: {str(e)}")
