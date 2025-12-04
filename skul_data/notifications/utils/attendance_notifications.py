from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from skul_data.notifications.models.notification import Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)


def send_attendance_notification(student, attendance, is_present=True):
    """
    Send attendance notification through multiple channels.

    Args:
        student: Student instance
        attendance: ClassAttendance instance
        is_present: Boolean indicating if student was present
    """
    # Get parent(s)
    parents = []
    if student.parent:
        parents.append(student.parent)
    parents.extend(list(student.guardians.all()))

    if not parents:
        logger.warning(f"No parent found for student {student.full_name}")
        return

    # Prepare notification data
    if is_present:
        title = f"✓ Attendance Confirmed: {student.full_name}"
        message = (
            f"Good news! {student.full_name} attended {attendance.school_class.name} "
            f"on {attendance.date.strftime('%B %d, %Y')}.\n\n"
            f"Class: {attendance.school_class.name}\n"
            f"Time: {attendance.created_at.strftime('%I:%M %p')}\n"
            f"Recorded by: {attendance.taken_by.get_full_name() if attendance.taken_by else 'System'}"
        )
        notification_type = "SYSTEM"
    else:
        title = f"⚠ Absence Alert: {student.full_name}"
        absence_reason = ""
        if attendance.notes:
            # Extract reason for this specific student from notes
            for line in attendance.notes.split("\n"):
                if student.full_name in line:
                    absence_reason = (
                        line.split(":", 1)[1].strip() if ":" in line else ""
                    )
                    break

        message = (
            f"{student.full_name} was marked absent from {attendance.school_class.name} "
            f"on {attendance.date.strftime('%B %d, %Y')}.\n\n"
            f"Class: {attendance.school_class.name}\n"
            f"Date: {attendance.date.strftime('%B %d, %Y')}\n"
        )

        if absence_reason:
            message += f"Reason: {absence_reason}\n"
        else:
            message += "Reason: Not specified\n"

        message += f"\nIf this is incorrect, please contact {attendance.taken_by.get_full_name() if attendance.taken_by else 'the school'}."
        notification_type = "EVENT"

    # Send to all parents/guardians
    for parent in parents:
        try:
            # 1. Create database notification
            notification = Notification.objects.create(
                user=parent.user,
                notification_type=notification_type,
                title=title,
                message=message,
                related_model="ClassAttendance",
                related_id=attendance.id,
            )

            # 2. Send WebSocket notification (real-time)
            send_websocket_notification(
                parent.user.id,
                {
                    "id": notification.id,
                    "type": notification_type,
                    "title": title,
                    "message": message,
                    "student_name": student.full_name,
                    "class_name": attendance.school_class.name,
                    "date": attendance.date.isoformat(),
                    "is_present": is_present,
                    "created_at": notification.created_at.isoformat(),
                },
            )

            # 3. Send Email notification
            send_attendance_email(
                parent,
                student,
                attendance,
                is_present,
                absence_reason if not is_present else None,
            )

            # 4. Optionally send SMS (if configured)
            if (
                hasattr(settings, "ENABLE_SMS_NOTIFICATIONS")
                and settings.ENABLE_SMS_NOTIFICATIONS
            ):
                send_attendance_sms(parent, student, attendance, is_present)

            logger.info(
                f"Attendance notification sent to {parent.user.email} for student {student.full_name}"
            )

        except Exception as e:
            logger.error(
                f"Failed to send attendance notification to {parent.user.email}: {str(e)}"
            )


def send_websocket_notification(user_id, notification_data):
    """Send real-time WebSocket notification"""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"notifications_{user_id}",
                {"type": "notification.message", "message": notification_data},
            )
    except Exception as e:
        logger.error(f"WebSocket notification failed for user {user_id}: {str(e)}")


def send_attendance_email(parent, student, attendance, is_present, absence_reason=None):
    """
    Send formatted email to parent about attendance.
    """
    try:
        # Get school info
        school = attendance.school_class.school

        # Prepare context for email template
        context = {
            "parent": parent,
            "student": student,
            "attendance": attendance,
            "school": school,
            "is_present": is_present,
            "absence_reason": absence_reason,
            "class_name": attendance.school_class.name,
            "date": attendance.date.strftime("%B %d, %Y"),
            "time": attendance.created_at.strftime("%I:%M %p"),
            "recorded_by": (
                attendance.taken_by.get_full_name() if attendance.taken_by else "System"
            ),
        }

        # Email subject
        if is_present:
            subject = f"✓ {student.full_name} - Attendance Confirmed"
        else:
            subject = f"⚠ {student.full_name} - Absence Alert"

        # Try to use HTML template, fall back to plain text
        try:
            html_message = render_to_string(
                "emails/attendance_notification.html", context
            )
            text_message = render_to_string(
                "emails/attendance_notification.txt", context
            )
        except:
            # Fallback to simple text message
            if is_present:
                text_message = (
                    f"Dear {parent.user.first_name},\n\n"
                    f"This is to confirm that {student.full_name} attended {attendance.school_class.name} "
                    f"on {context['date']}.\n\n"
                    f"Class: {attendance.school_class.name}\n"
                    f"Time: {context['time']}\n"
                    f"Recorded by: {context['recorded_by']}\n\n"
                    f"Best regards,\n{school.name}"
                )
            else:
                text_message = (
                    f"Dear {parent.user.first_name},\n\n"
                    f"{student.full_name} was marked absent from {attendance.school_class.name} "
                    f"on {context['date']}.\n\n"
                    f"Class: {attendance.school_class.name}\n"
                )
                if absence_reason:
                    text_message += f"Reason: {absence_reason}\n"
                text_message += (
                    f"\nIf this is incorrect, please contact the school immediately.\n\n"
                    f"Best regards,\n{school.name}"
                )
            html_message = None

        # Create email
        email = EmailMessage(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[parent.user.email],
            reply_to=[school.email] if hasattr(school, "email") else None,
        )

        if html_message:
            email.content_subtype = "html"
            email.body = html_message
            email.attach_alternative(text_message, "text/plain")

        email.send(fail_silently=False)
        logger.info(f"Attendance email sent to {parent.user.email}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to send attendance email to {parent.user.email}: {str(e)}"
        )
        return False


def send_attendance_sms(parent, student, attendance, is_present):
    """
    Send SMS notification (optional - requires Twilio or similar service).
    """
    if not hasattr(settings, "TWILIO_ACCOUNT_SID"):
        return False

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        if is_present:
            message = (
                f"{attendance.school_class.school.name}: {student.full_name} "
                f"attended {attendance.school_class.name} today."
            )
        else:
            message = (
                f"{attendance.school_class.school.name}: {student.full_name} "
                f"was absent from {attendance.school_class.name} today."
            )

        client.messages.create(
            body=message, from_=settings.TWILIO_PHONE_NUMBER, to=parent.phone_number
        )

        logger.info(f"Attendance SMS sent to {parent.phone_number}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to send attendance SMS to {parent.phone_number}: {str(e)}"
        )
        return False


def send_bulk_attendance_summary(parents_data, attendance_date, school):
    """
    Send daily attendance summary to parents (all their children's attendance).

    Args:
        parents_data: List of dicts with parent info and their children's attendance
        attendance_date: Date of attendance
        school: School instance
    """
    for parent_data in parents_data:
        try:
            parent = parent_data["parent"]
            children_attendance = parent_data[
                "children"
            ]  # List of {student, is_present, class_name, reason}

            # Create summary message
            summary = f"Daily Attendance Summary - {attendance_date.strftime('%B %d, %Y')}\n\n"

            for child_data in children_attendance:
                student = child_data["student"]
                is_present = child_data["is_present"]
                class_name = child_data["class_name"]
                reason = child_data.get("reason", "")

                status = "✓ Present" if is_present else "✗ Absent"
                summary += f"{student.full_name} ({class_name}): {status}"
                if reason:
                    summary += f" - {reason}"
                summary += "\n"

            summary += f"\n{school.name}"

            # Send email with summary
            email = EmailMessage(
                subject=f"Daily Attendance Summary - {attendance_date.strftime('%B %d, %Y')}",
                body=summary,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[parent.user.email],
            )
            email.send()

        except Exception as e:
            logger.error(f"Failed to send attendance summary: {str(e)}")
