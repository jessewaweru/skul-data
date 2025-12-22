from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from skul_data.users.models.password_reset import PasswordResetOTP

User = get_user_model()


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting a password reset.
    Accepts email and sends OTP.
    """

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Ensure the email exists in the system"""
        if not User.objects.filter(email=value).exists():
            # Don't reveal if email exists for security
            # But still validate format
            pass
        return value.lower()

    def save(self, **kwargs):
        """Create OTP and send email"""
        email = self.validated_data["email"]
        try:
            user = User.objects.get(email=email)

            # Get request context for IP and user agent
            request = self.context.get("request")
            ip_address = None
            user_agent = ""

            if request:
                ip_address = request.META.get("REMOTE_ADDR")
                user_agent = request.META.get("HTTP_USER_AGENT", "")

            # Create OTP
            otp = PasswordResetOTP.create_for_user(
                user=user, ip_address=ip_address, user_agent=user_agent
            )

            # Send email with OTP
            from django.core.mail import send_mail
            from django.conf import settings

            subject = "Password Reset OTP - Skul Data"
            message = f"""
Hello {user.get_full_name() or user.username},

You have requested to reset your password for Skul Data.

Your OTP code is: {otp.otp_code}

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

            return otp
        except User.DoesNotExist:
            # For security, don't reveal if user exists
            # Just return None silently
            return None


class PasswordResetVerifySerializer(serializers.Serializer):
    """
    Serializer for verifying OTP code.
    """

    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(required=True, max_length=6, min_length=6)

    def validate(self, data):
        """Verify the OTP is valid"""
        email = data.get("email")
        otp_code = data.get("otp_code")

        otp = PasswordResetOTP.verify_otp(email, otp_code)

        if not otp:
            raise serializers.ValidationError(
                {"otp_code": "Invalid or expired OTP code."}
            )

        data["otp"] = otp
        data["user"] = otp.user
        return data


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming password reset with new password.
    """

    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(required=True, max_length=6, min_length=6)
    new_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    confirm_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate(self, data):
        """Validate passwords match and OTP is valid"""
        # Check passwords match
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        # Verify OTP
        email = data.get("email")
        otp_code = data.get("otp_code")

        otp = PasswordResetOTP.verify_otp(email, otp_code)

        if not otp:
            raise serializers.ValidationError(
                {"otp_code": "Invalid or expired OTP code."}
            )

        # Validate password strength
        try:
            validate_password(data["new_password"], user=otp.user)
        except Exception as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})

        data["otp"] = otp
        data["user"] = otp.user
        return data

    def save(self, **kwargs):
        """Set the new password and mark OTP as used"""
        user = self.validated_data["user"]
        otp = self.validated_data["otp"]
        new_password = self.validated_data["new_password"]

        # Set new password
        user.set_password(new_password)
        user.save()

        # Mark OTP as used
        otp.mark_as_used()

        # Log security event
        from skul_data.schools.models.school import SecurityLog

        request = self.context.get("request")

        SecurityLog.objects.create(
            user=user,
            action_type="PASSWORD_CHANGE",
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
            details={"method": "password_reset", "timestamp": str(timezone.now())},
        )

        return user


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password when user is logged in.
    """

    old_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    confirm_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        """Verify the old password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, data):
        """Validate new passwords match"""
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        # Validate password strength
        user = self.context["request"].user
        try:
            validate_password(data["new_password"], user=user)
        except Exception as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})

        return data

    def save(self, **kwargs):
        """Set the new password"""
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()

        # Log security event
        from skul_data.schools.models.school import SecurityLog

        request = self.context["request"]

        SecurityLog.objects.create(
            user=user,
            action_type="PASSWORD_CHANGE",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            details={
                "method": "authenticated_change",
                "timestamp": str(timezone.now()),
            },
        )

        return user


from django.utils import timezone
