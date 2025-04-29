from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionLog


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

    ActionLog.objects.create(
        user=user,
        action=action,
        category=category,
        content_type=content_type,
        object_id=object_id,
        metadata=metadata or {},
    )
