from rest_framework.views import APIView
from skul_data.users.serializers.auth import (
    SchoolRegisterSerializer,
    SchoolLoginSerializer,
)
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


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
