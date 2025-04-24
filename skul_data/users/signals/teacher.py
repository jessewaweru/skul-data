from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from skul_data.users.models.teacher import Teacher

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
