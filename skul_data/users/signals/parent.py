from django.db.models.signals import post_save
from django.dispatch import receiver
from skul_data.users.models.parent import ParentStatusChange, ParentNotification
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.action_logs.utils.action_log import log_action


@receiver(post_save, sender=ParentStatusChange)
def log_parent_status_change(sender, instance, created, **kwargs):
    if created:  # We only care about creation for status changes
        log_action(
            user=instance.changed_by,
            action=f"Changed parent status from {instance.from_status} to {instance.to_status}",
            category=ActionCategory.UPDATE,
            obj=instance.parent,
            metadata={
                "reason": instance.reason,
                "changed_by": str(instance.changed_by),
                "status_change_id": instance.id,
            },
        )


@receiver(post_save, sender=ParentNotification)
def log_parent_notification(sender, instance, created, **kwargs):
    if created:
        log_action(
            user=instance.sent_by,
            action=f"Sent {instance.notification_type} notification to parent",
            category=ActionCategory.OTHER,
            obj=instance.parent,
            metadata={
                "message": instance.message,
                "related_student": (
                    str(instance.related_student) if instance.related_student else None
                ),
                "is_read": instance.is_read,
            },
        )
