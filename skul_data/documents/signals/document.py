from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from skul_data.documents.models.document import Document
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.action_logs.utils.action_log import log_action_async


@receiver(pre_save, sender=Document)
def track_document_changes(sender, instance, **kwargs):
    """Track field changes before saving"""
    print(f"Signal triggered for {sender.__name__}")

    if instance.pk:  # Only for updates
        try:
            old_instance = Document.objects.get(pk=instance.pk)
            changed_fields = []
            old_values = {}
            new_values = {}

            # Define fields to track
            tracked_fields = [
                "title",
                "description",
                "category",
                "is_public",
                "related_class",
            ]

            for field in tracked_fields:
                old_value = getattr(old_instance, field, None)
                new_value = getattr(instance, field, None)

                if old_value != new_value:
                    changed_fields.append(field)
                    old_values[field] = (
                        str(old_value) if old_value is not None else None
                    )
                    new_values[field] = (
                        str(new_value) if new_value is not None else None
                    )

            # Store changed fields on instance for post_save signal
            instance._changed_fields = changed_fields
            instance._old_values = old_values
            instance._new_values = new_values

        except Document.DoesNotExist:
            # This shouldn't happen, but handle gracefully
            pass


@receiver(post_save, sender=Document)
def log_document_action(sender, instance, created, **kwargs):
    """Log document create/update actions"""
    print(f"Signal triggered for {sender.__name__}")

    # Try to get current user from instance
    current_user = getattr(instance, "_current_user", None)

    if not current_user:
        # Try to get from uploaded_by for creation
        if created and instance.uploaded_by:
            current_user = instance.uploaded_by
        else:
            print(
                "No _current_user on instance, got from User.get_current_user(): None"
            )
            print("No user found, skipping action log")
            return
    else:
        print(f"Got _current_user from instance: {current_user}")

    if created:
        # Document creation
        metadata = {
            "title": instance.title,
            "category": instance.category.name if instance.category else None,
            "school": instance.school.name if instance.school else None,
            "file_size": instance.file_size,
            "file_type": instance.file_type,
            "is_public": instance.is_public,
        }

        action = f"Created document: {instance.title}"

        print(f"[DEBUG] log_action called with action: '{action}'")
        log_action_async(
            user=current_user,
            action=action,
            category=ActionCategory.CREATE,
            obj=instance,
            metadata=metadata,
        )
        print("Document creation logged successfully")

    else:
        # Document update
        changed_fields = getattr(instance, "_changed_fields", [])

        if changed_fields:
            old_values = getattr(instance, "_old_values", {})
            new_values = getattr(instance, "_new_values", {})

            metadata = {
                "fields_changed": changed_fields,
                "old_values": old_values,
                "new_values": new_values,
            }

            action = f"Updated document: {instance.title}"

            print(f"[DEBUG] log_action called with action: '{action}'")
            log_action_async(
                user=current_user,
                action=action,
                category=ActionCategory.UPDATE,
                obj=instance,
                metadata=metadata,
            )
            print("Document update logged successfully")
