from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from skul_data.school_timetables.models.school_timetable import Timetable, Lesson
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory


@receiver(pre_save, sender=Timetable)
def timetable_pre_save(sender, instance, **kwargs):
    """Ensure only one active timetable per class"""
    if instance.is_active:
        # Deactivate other active timetables for this class
        Timetable.objects.filter(
            school_class=instance.school_class, is_active=True
        ).exclude(pk=instance.pk).update(is_active=False)


@receiver(post_save, sender=Lesson)
def log_lesson_changes(sender, instance, created, **kwargs):
    """Log changes to lessons"""
    action = "Created lesson" if created else "Updated lesson"
    log_action(
        user=getattr(instance, "_current_user", None),
        action=action,
        category=ActionCategory.CREATE if created else ActionCategory.UPDATE,
        obj=instance,
        metadata={
            "timetable_id": instance.timetable.id,
            "subject": instance.subject.name,
            "teacher": str(instance.teacher),
            "time_slot": str(instance.time_slot),
        },
    )
