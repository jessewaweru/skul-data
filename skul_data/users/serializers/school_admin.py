from rest_framework import serializers
from django.contrib.auth import get_user_model
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.serializers.base_user import UserDetailSerializer
from skul_data.schools.serializers.school import SchoolSerializer
from skul_data.users.models.school_admin import AdministratorProfile

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


class AdministratorProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True
    )
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    # school_details = SchoolSerializer(source="school", read_only=True)
    full_name = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    # Add basic school info as nested fields (similar to user fields)
    school_id = serializers.IntegerField(source="school.id", read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = AdministratorProfile
        fields = [
            "id",
            "user_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "school",
            "school_id",
            "school_name",
            # "school_details",
            "position",
            "access_level",
            "is_active",
            "date_appointed",
            "permissions_granted",
            "notes",
            "last_login",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_full_name(self, obj):
        return obj.user.get_full_name()

    def create(self, validated_data):
        user_data = validated_data.pop("user", {})
        administrator = AdministratorProfile.objects.create(**validated_data)
        return administrator


class AdministratorProfileCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_type=User.ADMINISTRATOR),
        source="user",
        required=True,
    )
    position = serializers.CharField(required=True)
    access_level = serializers.ChoiceField(
        choices=AdministratorProfile.ACCESS_LEVEL_CHOICES, default="standard"
    )
    permissions_granted = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    class Meta:
        model = AdministratorProfile
        fields = [
            "user_id",
            "school",
            "position",
            "access_level",
            "permissions_granted",
            "notes",
        ]

    def validate_user_id(self, value):
        if hasattr(value, "administrator_profile"):
            raise serializers.ValidationError("This user is already an administrator")
        return value


class AdministratorProfileUpdateSerializer(serializers.ModelSerializer):
    position = serializers.CharField(required=False)
    access_level = serializers.ChoiceField(
        choices=AdministratorProfile.ACCESS_LEVEL_CHOICES, required=False
    )
    permissions_granted = serializers.ListField(
        child=serializers.CharField(), required=False
    )
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = AdministratorProfile
        fields = [
            "position",
            "access_level",
            "permissions_granted",
            "is_active",
            "notes",
        ]
