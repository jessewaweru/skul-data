from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.role import Role, Permission

User = get_user_model()


@receiver(pre_save, sender=Teacher)
def teacher_status_change(sender, instance, **kwargs):
    if instance.pk:
        original = Teacher.objects.get(pk=instance.pk)
        if original.status != instance.status:
            if instance.status == "TERMINATED":
                # Deactivate user account when teacher is terminated
                instance.user.is_active = False
                instance.user.save()
            elif instance.status == "ACTIVE" and original.status == "TERMINATED":
                # Reactivate user account if teacher is reinstated
                instance.user.is_active = True
                instance.user.save()


@receiver(post_save, sender=User)
def create_teacher_profile(sender, instance, created, **kwargs):
    if created and instance.user_type == "TEACHER":
        Teacher.objects.create(user=instance)


@receiver(post_save, sender=Teacher)
def assign_teacher_permissions(sender, instance, created, **kwargs):
    if created or not instance.user.role:
        user = instance.user
        user.user_type = User.TEACHER  # Ensure user_type is set

        # Get or create the permission
        perm, _ = Permission.objects.get_or_create(
            code="manage_attendance", defaults={"name": "Manage Attendance"}
        )

        # Create or get the default teacher role for this school
        role, _ = Role.objects.get_or_create(
            name="Class Teacher",
            school=instance.school,
            defaults={
                "role_type": "CUSTOM",
                "description": "Default role with basic teacher permissions",
            },
        )

        # Add permission if not already present
        if not role.permissions.filter(id=perm.id).exists():
            role.permissions.add(perm)

        # Assign role to user
        if user.role != role:
            user.role = role
            user.save()
