from django.core.mail import EmailMessage
from django.conf import settings
import logging


# Configure logger
logger = logging.getLogger(__name__)


def send_parent_email(parent, subject, message):
    """Send email to parent"""
    try:
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [parent.email],
        )
        email.send(fail_silently=False)
        return True
    except Exception as e:
        logger.error(f"Failed to send email to parent {parent.id}: {str(e)}")
        return False


# def send_parent_sms(parent, message):
#     """Send SMS to parent"""
#     try:
#         # In a real implementation, integrate with your SMS gateway
#         # This is just a placeholder
#         logger.info(f"Would send SMS to {parent.phone_number}: {message}")
#         return True
#     except Exception as e:
#         logger.error(f"Failed to send SMS to parent {parent.id}: {str(e)}")
#         return False
