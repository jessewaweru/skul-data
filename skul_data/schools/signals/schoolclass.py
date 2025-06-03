from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models import User
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.schools.models.schoolclass import ClassAttendance


@receiver(m2m_changed, sender=SchoolClass.students.through)
def log_student_class_changes(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    if action in ["post_add", "post_remove", "post_clear"]:
        user = getattr(instance, "_current_user", None) or User.get_current_user()
        if not user:
            return

        if action == "post_add":
            action_str = "Added students to class"
        elif action == "post_remove":
            action_str = "Removed students from class"
        else:
            action_str = "Cleared students from class"

        log_action(
            user=user,
            action=action_str,
            category=ActionCategory.UPDATE,
            obj=instance,
            metadata={
                "affected_students": list(pk_set) if pk_set else [],
                "action": action,
            },
        )


@receiver(m2m_changed, sender=ClassAttendance.present_students.through)
def log_attendance_changes(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action not in ["post_add", "post_remove", "post_clear"]:
        return

    user = getattr(instance, "_current_user", None) or User.get_current_user()

    log_action(
        user=user,
        action=f"Students {'added' if action == 'post_add' else 'removed'} from attendance",
        category=ActionCategory.UPDATE,
        obj=instance,
        metadata={
            "affected_students": list(pk_set) if pk_set else [],
            "total_present": instance.present_students.count(),
            "attendance_rate": instance.attendance_rate,
        },
    )
