from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from skul_data.users.models.role import Role, Permission
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.users.models.base_user import User
from rest_framework.response import Response
from rest_framework import status
from django.db.utils import DatabaseError
from django.db import transaction
from django.contrib.contenttypes.models import ContentType


@receiver(post_save, sender=Permission)
def log_permission_changes(sender, instance, created, **kwargs):
    """Log permission changes with validation"""
    try:
        user = User.get_current_user()

        action = "Created permission" if created else "Updated permission"
        metadata = {"code": instance.code, "name": instance.name}

        # Immediate logging in test mode
        from skul_data.action_logs.utils.action_log import _TEST_MODE

        if _TEST_MODE:
            return log_action(
                user=user,
                action=action,
                category=ActionCategory.CREATE if created else ActionCategory.UPDATE,
                obj=instance,
                metadata=metadata,
            )

        # Production behavior
        log_action(
            user=user,
            action=action,
            category=ActionCategory.CREATE if created else ActionCategory.UPDATE,
            obj=instance,
            metadata=metadata,
        )

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Failed to log permission change: {str(e)}")


@receiver(post_delete, sender=Permission)
def log_permission_deletion(sender, instance, **kwargs):
    """Log permission deletion with validation"""
    try:
        user = User.get_current_user()
        if not user or not user.pk:
            return

        log_action(
            user=user,
            action="Deleted permission",
            category=ActionCategory.DELETE,
            obj=instance,
            metadata={"code": instance.code, "name": instance.name},
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Failed to log permission deletion: {str(e)}")


@receiver(post_save, sender=Role)
def log_role_changes(sender, instance, created, **kwargs):
    """Log role creation/updates with proper transaction handling and validation"""
    try:
        # Get user context
        user = User.get_current_user()

        # Validate content type exists
        ContentType.objects.get_for_model(Role)

        action = "Created role" if created else "Updated role"
        metadata = {
            "name": instance.name,
            "role_type": instance.role_type,
            "school": str(instance.school) if instance.school else None,
        }

        # Immediate logging in test mode
        from skul_data.action_logs.utils.action_log import _TEST_MODE

        if _TEST_MODE:
            return log_action(
                user=user,
                action=action,
                category=ActionCategory.CREATE if created else ActionCategory.UPDATE,
                obj=instance,
                metadata=metadata,
            )

        # Production behavior with transaction handling
        def _create_log():
            log_action(
                user=user,
                action=action,
                category=ActionCategory.CREATE if created else ActionCategory.UPDATE,
                obj=instance,
                metadata=metadata,
            )

        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(_create_log)
        else:
            _create_log()

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Failed to log role change: {str(e)}")


@receiver(post_delete, sender=Role)
def log_role_deletion(sender, instance, **kwargs):
    """Log role deletion with validation"""
    try:
        user = User.get_current_user()
        if not user or not user.pk:
            return

        log_action(
            user=user,
            action="Deleted role",
            category=ActionCategory.DELETE,
            obj=instance,
            metadata={"name": instance.name, "school": str(instance.school)},
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Failed to log role deletion: {str(e)}")


@receiver(m2m_changed, sender=Role.permissions.through)
def log_permission_assignments(sender, instance, action, pk_set, **kwargs):
    """Log permission assignments to roles with validation"""
    if action not in ["post_add", "post_remove", "post_clear"]:
        return

    try:
        user = User.get_current_user()

        verb = {
            "post_add": "Added permissions to",
            "post_remove": "Removed permissions from",
            "post_clear": "Cleared all permissions from",
        }[action]

        permissions = Permission.objects.filter(pk__in=pk_set) if pk_set else []
        metadata = {
            "affected_permissions": [p.code for p in permissions],
            "total_permissions": instance.permissions.count(),
        }

        # Immediate logging in test mode
        from skul_data.action_logs.utils.action_log import _TEST_MODE

        if _TEST_MODE:
            return log_action(
                user=user,
                action=f"{verb} role {instance.name}",
                category=ActionCategory.UPDATE,
                obj=instance,
                metadata=metadata,
            )

        # Production behavior
        log_action(
            user=user,
            action=f"{verb} role {instance.name}",
            category=ActionCategory.UPDATE,
            obj=instance,
            metadata=metadata,
        )

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Failed to log permission assignment: {str(e)}")
