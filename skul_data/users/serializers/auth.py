from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from skul_data.users.models.superuser import SuperUser
from skul_data.schools.models.school import School


class SchoolRegisterSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(write_only=True)
    school_level = serializers.CharField(write_only=True)
    physical_address = serializers.CharField(write_only=True)
    phone_number = serializers.CharField()
    confirm_password = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "confirm_password",
            "school_name",
            "school_level",
            "physical_address",
        ]

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("passwords do not match")
        return data

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("confirm_password")

        email = validated_data.pop("email")
        school_name = validated_data.pop("school_name")
        school_level = validated_data.pop("school_level")
        address = validated_data.pop("physical_address")

        user = User.objects.create_user(username=email, email=email, password=password)
        school_code = f"{school_name[:3].upper()}{User.objects.count() + 1:03d}"
        superuser_profile = SuperUser.objects.create(
            user=user, school_name=school_name, school_code=school_code
        )

        # Next we create a corresponding School record
        School.objects.create(
            name=school_name,
            level=school_level,
            contact_phone=validated_data["phone_number"],
            location=address,
            code=school_code,
            superuser_profile=superuser_profile,
        )
        return user


class SchoolLoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid login credentials")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")

        data["user"] = user
        return user
