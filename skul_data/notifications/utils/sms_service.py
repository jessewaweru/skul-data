# skul_data/notifications/utils/sms_service.py
from django.conf import settings
import logging
import re
import africastalking

logger = logging.getLogger(__name__)


class AfricaTalkingSMSService:
    """
    SMS service using Africa's Talking API.
    Integrated with Skul Data notifications system.
    """

    def __init__(self):
        self.is_initialized = False
        self.initialize()

    def initialize(self):
        """Initialize Africa's Talking SDK"""
        try:
            username = getattr(settings, "AFRICASTALKING_USERNAME", "")
            api_key = getattr(settings, "AFRICASTALKING_API_KEY", "")

            if not username or not api_key:
                logger.warning("Africa's Talking credentials not configured")
                return

            africastalking.initialize(username, api_key)
            self.sms = africastalking.SMS
            self.is_initialized = True
            logger.info("Africa's Talking SMS initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Africa's Talking: {str(e)}")

    def send_sms(self, phone_number, message):
        """
        Send SMS via Africa's Talking

        Args:
            phone_number (str): Recipient phone number (Kenyan format)
            message (str): SMS message content

        Returns:
            dict: Result containing status and details
        """
        if not self.is_initialized:
            logger.warning("Africa's Talking not initialized - check credentials")
            return {
                "success": False,
                "error": "SMS service not initialized",
                "provider": "africas_talking",
            }

        try:
            # Format phone number
            formatted_number = self.format_phone_number(phone_number)

            if not formatted_number:
                return {
                    "success": False,
                    "error": "Invalid phone number",
                    "provider": "africas_talking",
                }

            # Send SMS
            response = self.sms.send(message, [formatted_number])

            logger.info(f"SMS sent to {formatted_number}")
            logger.debug(f"Africa's Talking response: {response}")

            # Parse response
            if (
                isinstance(response, dict)
                and "SMSMessageData" in response
                and "Recipients" in response["SMSMessageData"]
            ):

                recipient_data = response["SMSMessageData"]["Recipients"][0]
                status_code = recipient_data.get("statusCode", 0)

                # Status code 101 means success
                success = status_code == 101

                return {
                    "success": success,
                    "provider": "africas_talking",
                    "message_id": recipient_data.get("messageId", ""),
                    "status": recipient_data.get("status", "unknown"),
                    "status_code": status_code,
                    "cost": self.parse_cost(recipient_data.get("cost")),
                    "phone_number": formatted_number,
                    "response": response,
                }
            else:
                return {
                    "success": False,
                    "error": "Unexpected response format",
                    "response": response,
                    "provider": "africas_talking",
                }

        except Exception as e:
            logger.error(f"Africa's Talking SMS failed: {str(e)}")
            return {"success": False, "error": str(e), "provider": "africas_talking"}

    def format_phone_number(self, phone_number):
        """
        Format phone number for Africa's Talking.
        Accepts Kenyan phone numbers in various formats.

        Examples:
            0712345678 -> +254712345678
            712345678 -> +254712345678
            +254712345678 -> +254712345678
            254712345678 -> +254712345678
        """
        if not phone_number:
            logger.warning("Empty phone number provided")
            return None

        # Remove any non-digit characters except +
        cleaned = "".join(c for c in str(phone_number) if c.isdigit() or c == "+")

        # Handle different formats
        if cleaned.startswith("+254"):
            # Already in correct format
            return cleaned
        elif cleaned.startswith("254"):
            # Add + prefix
            return "+" + cleaned
        elif cleaned.startswith("0"):
            # Replace leading 0 with +254
            return "+254" + cleaned[1:]
        elif len(cleaned) == 9:
            # Assume missing leading 0 (e.g., 712345678)
            return "+254" + cleaned
        else:
            logger.warning(f"Could not format phone number: {phone_number}")
            return None

    def parse_cost(self, cost_string):
        """
        Parse cost string from Africa's Talking response.
        Example: 'KES 0.8000' -> 0.8
        """
        if not cost_string:
            return 0.0

        try:
            # Extract numeric value
            match = re.search(r"(\d+\.?\d*)", str(cost_string))
            if match:
                return float(match.group(1))
            return 0.0
        except (ValueError, TypeError):
            return 0.0

    # ========================================================================
    # Skul Data Specific SMS Templates
    # ========================================================================

    def send_verification_code(self, phone_number, otp_code):
        """Send phone verification OTP"""
        message = (
            f"Your Skul Data verification code is: {otp_code}\n"
            f"This code expires in 10 minutes.\n"
            f"Do not share this code with anyone."
        )
        return self.send_sms(phone_number, message)

    def send_welcome_sms(self, phone_number, school_name, username, temp_password):
        """Send welcome SMS with login credentials"""
        message = (
            f"Welcome to Skul Data!\n"
            f"School: {school_name}\n"
            f"Username: {username}\n"
            f"Password: {temp_password}\n"
            f"Login at: skuldata.com\n"
            f"Change your password after first login."
        )
        return self.send_sms(phone_number, message)

    def send_password_reset_code(self, phone_number, otp_code):
        """Send password reset OTP"""
        message = (
            f"Your Skul Data password reset code is: {otp_code}\n"
            f"Valid for 10 minutes.\n"
            f"If you didn't request this, please ignore."
        )
        return self.send_sms(phone_number, message)

    def send_account_activation_reminder(self, phone_number, school_name):
        """Remind user to activate their account"""
        message = (
            f"Reminder: Activate your Skul Data account for {school_name}.\n"
            f"Check your email for the activation link.\n"
            f"Need help? Contact support."
        )
        return self.send_sms(phone_number, message)

    def send_attendance_alert(self, phone_number, student_name, status, class_name):
        """Send attendance notification to parent"""
        if status == "present":
            message = (
                f"{student_name} attended {class_name} today.\n" f"Skul Data Attendance"
            )
        else:
            message = (
                f"ALERT: {student_name} was absent from {class_name} today.\n"
                f"Please contact the school if this is incorrect."
            )
        return self.send_sms(phone_number, message)

    def send_fee_reminder(self, phone_number, student_name, amount, due_date):
        """Send fee payment reminder"""
        message = (
            f"Fee Reminder: {student_name}\n"
            f"Amount: KES {amount}\n"
            f"Due: {due_date}\n"
            f"Pay via M-Pesa or contact school office."
        )
        return self.send_sms(phone_number, message)

    def send_report_ready_notification(self, phone_number, student_name, report_type):
        """Notify parent that report is ready"""
        message = (
            f"{student_name}'s {report_type} is now available.\n"
            f"Login to Skul Data to view: skuldata.com\n"
            f"Contact school if you need assistance."
        )
        return self.send_sms(phone_number, message)

    def send_event_reminder(self, phone_number, event_name, event_date):
        """Send school event reminder"""
        message = (
            f"Event Reminder: {event_name}\n"
            f"Date: {event_date}\n"
            f"Check Skul Data for more details."
        )
        return self.send_sms(phone_number, message)


# Global instance
sms_service = AfricaTalkingSMSService()


# ========================================================================
# Convenience Functions (for easy importing)
# ========================================================================


def send_verification_code(phone_number, otp_code):
    """Send verification code via SMS"""
    return sms_service.send_verification_code(phone_number, otp_code)


def send_welcome_message(phone_number, school_name, username, temp_password):
    """Send welcome message with credentials"""
    return sms_service.send_welcome_sms(
        phone_number, school_name, username, temp_password
    )


def send_password_reset_code(phone_number, otp_code):
    """Send password reset code via SMS"""
    return sms_service.send_password_reset_code(phone_number, otp_code)


def send_attendance_notification(phone_number, student_name, status, class_name):
    """Send attendance notification to parent"""
    return sms_service.send_attendance_alert(
        phone_number, student_name, status, class_name
    )


def send_fee_reminder(phone_number, student_name, amount, due_date):
    """Send fee payment reminder"""
    return sms_service.send_fee_reminder(phone_number, student_name, amount, due_date)


def send_report_notification(phone_number, student_name, report_type):
    """Send report ready notification"""
    return sms_service.send_report_ready_notification(
        phone_number, student_name, report_type
    )


def send_event_reminder(phone_number, event_name, event_date):
    """Send event reminder"""
    return sms_service.send_event_reminder(phone_number, event_name, event_date)
