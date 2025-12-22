from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from django.utils import timezone
from skul_data.users.serializers.password_reset import (
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
)


class PasswordResetRateThrottle(AnonRateThrottle):
    """
    Custom throttle for password reset requests.
    Limits to 3 requests per hour per IP.
    """

    rate = "3/hour"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle])
def password_reset_request(request):
    """
    Request a password reset OTP.

    POST /api/users/password-reset/request/
    Body: {"email": "user@example.com"}

    Returns: 200 with success message (even if email doesn't exist for security)
    """
    serializer = PasswordResetRequestSerializer(
        data=request.data, context={"request": request}
    )

    if serializer.is_valid():
        serializer.save()

        # Always return success for security (don't reveal if email exists)
        return Response(
            {
                "message": "If an account exists with this email, you will receive an OTP code shortly.",
                "detail": "Please check your email for the OTP code. It will expire in 10 minutes.",
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_verify(request):
    """
    Verify OTP code without changing password yet.
    Useful for two-step reset process.

    POST /api/users/password-reset/verify/
    Body: {
        "email": "user@example.com",
        "otp_code": "123456"
    }

    Returns: 200 if OTP is valid, 400 if invalid
    """
    serializer = PasswordResetVerifySerializer(data=request.data)

    if serializer.is_valid():
        return Response(
            {
                "message": "OTP verified successfully.",
                "detail": "You can now set your new password.",
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle])
def password_reset_confirm(request):
    """
    Confirm password reset with OTP and set new password.

    POST /api/users/password-reset/confirm/
    Body: {
        "email": "user@example.com",
        "otp_code": "123456",
        "new_password": "newpassword123",
        "confirm_password": "newpassword123"
    }

    Returns: 200 with success message if password changed
    """
    serializer = PasswordResetConfirmSerializer(
        data=request.data, context={"request": request}
    )

    if serializer.is_valid():
        user = serializer.save()

        return Response(
            {
                "message": "Password reset successfully.",
                "detail": "You can now login with your new password.",
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change password for authenticated user.

    POST /api/users/change-password/
    Body: {
        "old_password": "currentpassword",
        "new_password": "newpassword123",
        "confirm_password": "newpassword123"
    }

    Requires: Authentication (Bearer token)
    Returns: 200 with success message
    """
    serializer = ChangePasswordSerializer(
        data=request.data, context={"request": request}
    )

    if serializer.is_valid():
        serializer.save()

        return Response(
            {
                "message": "Password changed successfully.",
                "detail": "Your password has been updated. Please use it for future logins.",
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout user and invalidate tokens.

    POST /api/users/logout/
    Requires: Authentication (Bearer token)

    This will:
    1. Log the logout action
    2. Invalidate the refresh token (if using token blacklist)
    3. Clear any session data
    """
    from skul_data.schools.models.school import SecurityLog
    from rest_framework_simplejwt.tokens import RefreshToken

    user = request.user

    # Log security event
    SecurityLog.objects.create(
        user=user,
        action_type="LOGOUT",
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        details={"timestamp": str(timezone.now()), "method": "api_logout"},
    )

    # If refresh token is provided, blacklist it
    refresh_token = request.data.get("refresh_token")
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as e:
            pass  # Token might already be blacklisted or invalid

    return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_password_strength(request):
    """
    Check if a password meets strength requirements without saving.

    GET /api/users/check-password-strength/?password=testpassword123

    Returns: Password strength analysis
    """
    from django.contrib.auth.password_validation import (
        validate_password,
        password_validators_help_texts,
    )

    password = request.query_params.get("password", "")

    if not password:
        return Response(
            {"error": "Password parameter is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(password, user=request.user)
        return Response(
            {
                "valid": True,
                "message": "Password meets all requirements",
                "requirements": password_validators_help_texts(),
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {
                "valid": False,
                "errors": list(e.messages),
                "requirements": password_validators_help_texts(),
            },
            status=status.HTTP_200_OK,
        )
