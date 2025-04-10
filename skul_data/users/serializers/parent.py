from rest_framework import serializers
from skul_data.users.models.parent import Parent
from django.contrib.auth import get_user_model

User = get_user_model()


class ParentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Parent
        fields = ["id", "username", "email", "phone_number", "school", "children"]
        # If you need to make some fields writeable, add them to extra_kwargs
        extra_kwargs = {
            "school": {"required": True},
        }
