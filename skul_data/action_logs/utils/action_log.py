import uuid, os, sys
from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionLog
from django.db import transaction
import threading
import logging
from skul_data.users.models.base_user import User
from django.conf import settings
import json
from decimal import Decimal
from datetime import date, datetime

logger = logging.getLogger(__name__)

# Global flag for test mode - can be set by tests
_TEST_MODE = False


def set_test_mode(enabled=True):
    """Set test mode for action logging - use this in your test setup"""
    global _TEST_MODE
    _TEST_MODE = enabled


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal, date, and datetime objects"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)  # Convert Decimal to float for JSON
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()  # Convert date/datetime to ISO format
        elif hasattr(obj, "pk"):  # Model instance
            return {"model": obj.__class__.__name__, "id": obj.pk, "str": str(obj)}
        # Let the base class default method raise the TypeError
        return super().default(obj)


def log_action(user, action, category, obj=None, metadata=None):
    """
    Helper function to manually log actions with robust error handling
    """
    # Check both global test mode AND Django settings
    test_mode_enabled = _TEST_MODE or getattr(settings, "ACTION_LOG_TEST_MODE", False)

    # Skip logging only if not in test mode (unless test mode is explicitly enabled)
    if not test_mode_enabled and ("test" in sys.argv or "TEST" in os.environ):
        return None

    try:
        # Validate user exists and is saved
        if user and user.pk:
            # Use select_for_update to ensure user exists and is committed
            try:
                User.objects.filter(pk=user.pk).exists()
            except Exception:
                # If user check fails, skip logging rather than crash
                return None
        elif user and not user.pk:
            # User is not saved yet, skip logging
            return None

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
            try:
                # Use our custom JSON encoder to handle Decimal and other non-serializable types
                processed_metadata = json.loads(
                    json.dumps(metadata, cls=CustomJSONEncoder)
                )
            except Exception as e:
                # If serialization fails, create a simplified version
                logger.warning(f"Failed to serialize metadata: {str(e)}")
                processed_metadata = {
                    "error": "Failed to serialize metadata",
                    "original_action": action,
                }

                # Try to create a basic representation
                try:
                    for key, value in metadata.items():
                        if isinstance(value, (int, float, str, bool, type(None))):
                            processed_metadata[key] = value
                        elif isinstance(value, Decimal):
                            processed_metadata[key] = float(value)
                        elif isinstance(value, (date, datetime)):
                            processed_metadata[key] = value.isoformat()
                        elif hasattr(value, "pk"):
                            processed_metadata[key] = {
                                "model": value.__class__.__name__,
                                "id": value.pk,
                            }
                        else:
                            processed_metadata[key] = str(value)
                except Exception as e2:
                    logger.error(f"Failed to create basic metadata: {str(e2)}")

        action_log = ActionLog.objects.create(
            user=user,
            user_tag=user_tag,
            action=action,
            category=category,
            content_type=content_type,
            object_id=object_id,
            metadata=processed_metadata or {},
        )
        return action_log

    except Exception as e:
        # Log the error but don't crash the main operation
        logger.warning(f"Failed to create action log: {str(e)}")
        return None


def log_action_async(user, action, category, obj=None, metadata=None):
    """
    Non-blocking action logger for high-frequency operations.
    Queues the log to be created after the current transaction succeeds.
    """
    test_mode_enabled = _TEST_MODE or getattr(settings, "ACTION_LOG_TEST_MODE", False)

    def create_log():
        try:
            log_action(user, action, category, obj, metadata)
        except Exception as e:
            logger.error(f"Async action log failed: {str(e)}")

    # In test mode, always execute synchronously regardless of transaction state
    if test_mode_enabled:
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
