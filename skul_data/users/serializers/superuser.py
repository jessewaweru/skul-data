from rest_framework import serializers
from skul_data.users.models.superuser import SuperUser


class SuperUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuperUser
        fields = ["id", "username", "email", "school_name", "school_code"]
