# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.utils import timezone
# from skul_data.scheduler.models.scheduler import SchoolEvent, EventRSVP


# @receiver(post_save, sender=SchoolEvent)
# def notify_event_creation(sender, instance, created, **kwargs):
#     if created:
#         # Get all target users
#         users = instance.get_target_users()

#         # Create notifications
#         notifications = [
#             Notification(
#                 user=user,
#                 title=f"New Event: {instance.title}",
#                 message=instance.description or "No additional details",
#                 notification_type="EVENT",
#                 related_model="SchoolEvent",
#                 related_id=instance.id,
#                 action_url=f"/calendar/events/{instance.id}/",
#             )
#             for user in users
#         ]

#         Notification.objects.bulk_create(notifications)


# @receiver(post_save, sender=EventRSVP)
# def notify_rsvp_update(sender, instance, created, **kwargs):
#     if created:
#         Notification.objects.create(
#             user=instance.event.created_by,
#             title=f"New RSVP for {instance.event.title}",
#             message=f"{instance.user.get_full_name()} is {instance.get_status_display()}",
#             notification_type="RSVP",
#             related_model="SchoolEvent",
#             related_id=instance.event.id,
#             action_url=f"/calendar/events/{instance.event.id}/rsvps/",
#         )
