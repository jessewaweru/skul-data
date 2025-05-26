from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionLog
import uuid


# def log_action(user, action, category, obj=None, metadata=None):
#     """
#     Helper function to manually log actions

#     Args:
#         user: User instance who performed the action
#         action: Description of the action (string)
#         category: Action category (from ActionCategory)
#         obj: Optional related object being acted upon
#         metadata: Additional context as a dictionary
#     """
#     content_type = None
#     object_id = None

#     if obj:
#         content_type = ContentType.objects.get_for_model(obj)
#         object_id = obj.pk

#     # Set user_tag based on user or use a default system tag
#     user_tag = (
#         user.user_tag if user else uuid.UUID("00000000-0000-0000-0000-000000000000")
#     )

#     ActionLog.objects.create(
#         user=user,
#         user_tag=user_tag,
#         action=action,
#         category=category,
#         content_type=content_type,
#         object_id=object_id,
#         metadata=metadata or {},
#     )


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

    ActionLog.objects.create(
        user=user,
        user_tag=user_tag,
        action=action,
        category=category,
        content_type=content_type,
        object_id=object_id,
        metadata=processed_metadata or {},
    )
