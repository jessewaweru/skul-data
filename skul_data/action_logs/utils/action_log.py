import uuid
from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionLog
from django.db import transaction
import threading
import logging

logger = logging.getLogger(__name__)


# Global flag for test mode - can be set by tests
_TEST_MODE = False


def set_test_mode(enabled=True):
    """Set test mode for action logging - use this in your test setup"""
    global _TEST_MODE
    _TEST_MODE = enabled


def log_action(user, action, category, obj=None, metadata=None):
    """
    Helper function to manually log actions

    Args:
        user: User instance who performed the action
        action: Description of the action (string)
        category: Action category (from ActionCategory)
        obj: Optional related object being acted upon
        metadata: Additional context as a dictionary
    """
    content_type = None
    object_id = None

    if obj:
        content_type = ContentType.objects.get_for_model(obj)
        object_id = obj.pk

    # Set user_tag based on user or use a default system tag
    user_tag = (
        user.user_tag if user else uuid.UUID("00000000-0000-0000-0000-000000000000")
    )

    # Process metadata to ensure JSON serialization
    processed_metadata = {}
    if metadata:
        for key, value in metadata.items():
            if hasattr(value, "pk"):  # If it's a model instance
                processed_metadata[key] = {
                    "model": value.__class__.__name__,
                    "id": value.pk,
                    "str": str(value),
                }
            elif isinstance(value, (list, tuple, set)):
                processed_metadata[key] = [
                    (
                        {"model": v.__class__.__name__, "id": v.pk, "str": str(v)}
                        if hasattr(v, "pk")
                        else v
                    )
                    for v in value
                ]
            elif isinstance(value, dict):
                processed_metadata[key] = {
                    k: (
                        {"model": v.__class__.__name__, "id": v.pk, "str": str(v)}
                        if hasattr(v, "pk")
                        else v
                    )
                    for k, v in value.items()
                }
            else:
                processed_metadata[key] = value

    action_log = ActionLog.objects.create(
        user=user,
        user_tag=user_tag,
        action=action,
        category=category,
        content_type=content_type,
        object_id=object_id,
        metadata=processed_metadata or {},
    )


def log_action_async(user, action, category, obj=None, metadata=None):
    """
    Non-blocking action logger for high-frequency operations.
    Queues the log to be created after the current transaction succeeds.

    Args:
        Same as log_action()
    """
    global _TEST_MODE

    def create_log():
        try:
            log_action(user, action, category, obj, metadata)
        except Exception as e:
            logger.error(f"Async action log failed: {str(e)}")

    # In test mode, always execute synchronously regardless of transaction state
    if _TEST_MODE:
        create_log()
        return

    # If we're NOT in an atomic block (autocommit is True), execute immediately
    if transaction.get_autocommit():
        # In production, use threading for true async behavior
        thread = threading.Thread(target=create_log)
        thread.daemon = True  # Make thread non-blocking for program exit
        thread.start()
    else:
        # Will execute after transaction completes
        transaction.on_commit(create_log)


def log_system_action(action, category, obj=None, metadata=None):
    """Log system operations without user context"""
    log_action(
        user=None,
        action=action,
        category=category,
        obj=obj,
        metadata={"system_operation": True, **(metadata or {})},
    )
