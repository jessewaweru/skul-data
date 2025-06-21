from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db import transaction
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.role import Permission
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.action_logs.utils.action_log import log_action

User = get_user_model()


@receiver(pre_save, sender=Teacher)
def teacher_status_change(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        original = Teacher.objects.get(pk=instance.pk)
    except Teacher.DoesNotExist:
        return

    if original.status != instance.status:
        # Get current user from the instance if set, otherwise try to get from thread local
        current_user = getattr(instance, "_current_user", None)
        if not current_user:
            try:
                current_user = User.get_current_user()
            except:
                current_user = None

        metadata = {
            "previous_status": original.status,
            "new_status": instance.status,
            "teacher_id": instance.id,
        }

        # Log status change first
        log_action(
            user=current_user,
            action=f"Changed teacher status from {original.status} to {instance.status}",
            category=ActionCategory.UPDATE,
            obj=instance,
            metadata=metadata,
        )

        # Then handle user activation/deactivation
        if instance.status == "TERMINATED" and original.status != "TERMINATED":
            if instance.user.is_active:  # Only if user is currently active
                instance.user.is_active = False
                instance.user.save()
                log_action(
                    user=current_user,
                    action="Deactivated user account due to teacher termination",
                    category=ActionCategory.UPDATE,
                    obj=instance.user,
                    metadata={**metadata, "user_deactivated": True},
                )
        elif original.status == "TERMINATED" and instance.status != "TERMINATED":
            if not instance.user.is_active:  # Only if user is currently inactive
                instance.user.is_active = True
                instance.user.save()
                log_action(
                    user=current_user,
                    action="Reactivated user account due to teacher status change",
                    category=ActionCategory.UPDATE,
                    obj=instance.user,
                    metadata={**metadata, "user_reactivated": True},
                )


@receiver(post_save, sender=Teacher)
def assign_teacher_permissions(sender, instance, created, **kwargs):
    if created or not instance.user.role:
        user = instance.user
        user.user_type = User.TEACHER

        # Get or create the permission
        from skul_data.users.models.role import Role

        perm, _ = Permission.objects.get_or_create(
            code="manage_attendance", defaults={"name": "Manage Attendance"}
        )

        # Create or get the default teacher role
        role, _ = Role.objects.get_or_create(
            name="Class Teacher",
            school=instance.school,
            defaults={
                "role_type": "CUSTOM",
            },
        )

        # Add permission if not already present
        if not role.permissions.filter(id=perm.id).exists():
            role.permissions.add(perm)

        # Assign role to user
        if user.role != role:
            user.role = role
            user.save()


@receiver(pre_save, sender=Teacher)
def log_teacher_admin_status(sender, instance, **kwargs):
    """Log changes to teacher's administrator status"""
    if not instance.pk:  # New instance, no previous state
        return

    try:
        old_instance = Teacher.objects.get(pk=instance.pk)
        if old_instance.is_administrator != instance.is_administrator:
            # Get the current user
            from skul_data.users.models.base_user import User

            user = User.get_current_user()

            if user:
                action = (
                    f"Made teacher {instance.user.get_full_name()} an administrator"
                    if instance.is_administrator
                    else f"Removed administrator status from teacher {instance.user.get_full_name()}"
                )

                # Debug print
                print(
                    f"DEBUG: old_status={old_instance.is_administrator}, new_status={instance.is_administrator}"
                )

                def create_log():
                    try:
                        log_action(
                            user=user,
                            action=action,
                            category=ActionCategory.UPDATE,
                            obj=instance,
                            metadata={
                                "action_type": "TEACHER_ADMIN_STATUS_CHANGE",
                                "previous_status": old_instance.is_administrator,
                                "new_status": instance.is_administrator,
                                "administrator_since": (
                                    instance.administrator_since.isoformat()
                                    if instance.is_administrator
                                    and instance.administrator_since
                                    else None
                                ),
                                "administrator_until": (
                                    instance.administrator_until.isoformat()
                                    if not instance.is_administrator
                                    and instance.administrator_until
                                    else None
                                ),
                                "school_id": (
                                    instance.school.id if instance.school else None
                                ),
                            },
                        )
                    except Exception as e:
                        print(f"DEBUG: Logging failed: {e}")

                # For tests, execute immediately without transaction.on_commit
                from skul_data.action_logs.utils.action_log import _TEST_MODE

                if _TEST_MODE:
                    create_log()
                else:
                    transaction.on_commit(create_log)
    except Teacher.DoesNotExist:
        pass  # Instance doesn't exist yet
