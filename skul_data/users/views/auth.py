from rest_framework.views import APIView
from skul_data.users.serializers.auth import (
    SchoolRegisterSerializer,
    SchoolLoginSerializer,
)
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from skul_data.users.models.verification import AccountActivation
from django.contrib.auth import get_user_model


class SchoolRegisterAPIView(APIView):
    def post(self, request):
        serializer = SchoolRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "School registered successfully"}, status=201)
        return Response(serializer.errors, status=400)


class SchoolLoginAPIView(APIView):
    def post(self, request):
        serializer = SchoolLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "username": user.username,
                    "email": user.email,
                    "user_type": user.user_type,
                },
                status=200,
            )
        return Response(serializer.errors, status=400)


@api_view(["GET"])
@permission_classes([AllowAny])
def activate_account(request, token):
    """
    Activate user account using activation token.

    GET /api/users/activate-account/{token}/

    Returns: User details and success message
    """
    try:
        # Find activation record
        activation = AccountActivation.objects.select_related("user").get(token=token)

        # Check if already activated
        if activation.is_activated:
            return Response(
                {
                    "message": "This account has already been activated.",
                    "detail": "Please proceed to login.",
                    "user": {
                        "name": activation.user.get_full_name(),
                        "email": activation.user.email,
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Check if expired
        if not activation.is_valid():
            return Response(
                {
                    "error": "Activation link has expired.",
                    "detail": "Please contact support to get a new activation link.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Activate the account
        activation.mark_as_activated()

        # Log security event
        from skul_data.schools.models.school import SecurityLog

        SecurityLog.objects.create(
            user=activation.user,
            action_type="LOGIN",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            details={"action": "account_activated", "method": "activation_link"},
        )

        return Response(
            {
                "message": "Account activated successfully!",
                "detail": "You can now login with your credentials.",
                "user": {
                    "name": activation.user.get_full_name(),
                    "email": activation.user.email,
                    "username": activation.user.username,
                },
            },
            status=status.HTTP_200_OK,
        )

    except AccountActivation.DoesNotExist:
        return Response(
            {
                "error": "Invalid activation link.",
                "detail": "The activation link is invalid or has been used. Please contact support.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except Exception as e:
        return Response(
            {"error": "Activation failed.", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
