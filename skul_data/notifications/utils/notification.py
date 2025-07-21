# skul_data/notifications/utils/notifications.py
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from twilio.rest import Client  # For SMS - optional if you won't use SMS


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
    Send SMS to parent (requires Twilio or other SMS service configuration).
    Optional - only implement if you need SMS functionality.
    """
    if not hasattr(settings, "TWILIO_ACCOUNT_SID"):
        return False  # SMS not configured

    if context:
        message = message.format(**context)

    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message, from_=settings.TWILIO_PHONE_NUMBER, to=parent.phone_number
        )
        return True
    except Exception as e:
        # Log error
        from django.utils.log import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send SMS to {parent.phone_number}: {str(e)}")
        return False
