from rest_framework import serializers
from django.contrib.auth import get_user_model
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.serializers.base_user import UserDetailSerializer

User = get_user_model()


class SchoolAdminSerializer(serializers.ModelSerializer):
    user_details = UserDetailSerializer(source="user", read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = SchoolAdmin
        fields = [
            "id",
            "user",
            "user_details",
            "school",
            "school_name",
            "is_primary",
        ]
        extra_kwargs = {"user": {"write_only": True}, "school": {"write_only": True}}


class SchoolAdminCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)

    class Meta:
        model = SchoolAdmin
        fields = ["email", "first_name", "last_name", "school", "is_primary"]

    def create(self, validated_data):
        # Create user first
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            user_type=User.SCHOOL_ADMIN,
        )

        # Then create admin profile
        return SchoolAdmin.objects.create(
            user=user,
            school=validated_data["school"],
            is_primary=validated_data.get("is_primary", False),
        )
