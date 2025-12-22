from celery import shared_task
from django.utils import timezone
from skul_data.users.models.password_reset import PasswordResetOTP
import logging

logger = logging.getLogger(__name__)


@shared_task(name="skul_data.users.tasks.cleanup_expired_otps")
def cleanup_expired_otps():
    """
    Celery task to clean up expired OTP records.
    Runs daily at 2:00 AM (configured in settings).

    This helps maintain database cleanliness and performance.
    """
    try:
        # Delete OTPs that are older than 24 hours
        cutoff_time = timezone.now() - timezone.timedelta(hours=24)

        deleted_count, _ = PasswordResetOTP.objects.filter(
            created_at__lt=cutoff_time
        ).delete()

        logger.info(f"Cleaned up {deleted_count} expired OTP records")

        return {
            "status": "success",
            "deleted_count": deleted_count,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error cleaning up expired OTPs: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": timezone.now().isoformat(),
        }


@shared_task(name="skul_data.users.tasks.send_password_reset_email")
def send_password_reset_email(user_id, otp_code):
    """
    Async task to send password reset email.
    This can be used if you want to make email sending asynchronous.
    """
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings

    User = get_user_model()

    try:
        user = User.objects.get(id=user_id)

        subject = "Password Reset OTP - Skul Data"
        message = f"""
Hello {user.get_full_name() or user.username},

You have requested to reset your password for Skul Data.

Your OTP code is: {otp_code}

This code will expire in 10 minutes.

If you did not request this password reset, please ignore this email and ensure your account is secure.

Best regards,
Skul Data Team
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(f"Password reset email sent to {user.email}")

        return {
            "status": "success",
            "email": user.email,
            "timestamp": timezone.now().isoformat(),
        }
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
        return {"status": "error", "error": "User not found"}
    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        return {"status": "error", "error": str(e)}
