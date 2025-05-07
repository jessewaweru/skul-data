from django.core.mail import EmailMessage
from django.conf import settings
import logging

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


# Configure logger
logger = logging.getLogger(__name__)


def send_parent_email(parent, subject, message):
    """Send email to parent"""
    try:
        # Validate email format first
        validate_email(parent.email)

        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [parent.email],
        )
        email.send(fail_silently=False)
        return True
    except ValidationError:
        logger.error(f"Invalid email format for parent {parent.id}: {parent.email}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email to parent {parent.id}: {str(e)}")
        return False
