from rest_framework import serializers
from skul_data.users.models.superuser import SuperUser
from django.contrib.auth import get_user_model

User = get_user_model()


class SuperUserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = SuperUser
        fields = ["id", "username", "email", "school_name", "school_code"]
