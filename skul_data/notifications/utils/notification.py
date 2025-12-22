# skul_data/notifications/utils/notifications.py
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
import logging
from skul_data.notifications.utils import sms_service

logger = logging.getLogger(__name__)


def send_parent_email_fees(parent, subject, message, context=None, attachment=None):
    """
    Send email to a parent with optional template rendering and attachment.

    Args:
        parent: Parent model instance
        subject: Email subject
        message: Plain text or template path
        context: Dictionary for template rendering
        attachment: Tuple of (filename, content, mime_type)
    """
    if context is None:
        context = {}

    # Add default context
    context.setdefault("parent", parent)
    context.setdefault("student", parent.children.first())
    context.setdefault("school", parent.school)

    # Render template if message ends with .txt
    if isinstance(message, str) and message.endswith(".txt"):
        message = render_to_string(message, context)

    email = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [parent.user.email],
    )

    if attachment:
        email.attach(*attachment)

    try:
        email.send()
        return True
    except Exception as e:
        # Log error
        from django.utils.log import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send email to {parent.user.email}: {str(e)}")
        return False


def send_parent_sms(parent, message, context=None):
    """
    Wrapper function compatible with existing notification.py interface.
    Can be used as a drop-in replacement.

    Args:
        parent: Parent model instance
        message: SMS message text (will be formatted if context provided)
        context: Dictionary for string formatting
    """
    if not parent or not hasattr(parent, "phone_number"):
        logger.warning(f"Parent has no phone number: {parent}")
        return False

    if context:
        try:
            message = message.format(**context)
        except KeyError as e:
            logger.error(f"Missing context key for SMS: {e}")

    result = sms_service.send_sms(parent.phone_number, message)
    return result.get("success", False)
