from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from skul_data.schools.models.school import School
from skul_data.users.models.school_admin import SchoolAdmin


class SchoolRegisterSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(write_only=True, required=True)
    school_type = serializers.ChoiceField(
        choices=School.SCHOOL_TYPES, write_only=True, default="PRI"
    )
    address = serializers.CharField(write_only=True)
    city = serializers.CharField(write_only=True)
    country = serializers.CharField(write_only=True, default="Kenya")
    phone = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    website = serializers.URLField(write_only=True, required=False)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "school_name",
            "school_type",
            "address",
            "city",
            "country",
            "phone",
            "email",
            "website",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
        ]

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match")
        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError("Email already exists")
        return data

    def create(self, validated_data):
        # Create User
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            user_type=User.SCHOOL_ADMIN,
            is_staff=True,
        )

        # Create School
        school = School.objects.create(
            name=validated_data["school_name"],
            type=validated_data["school_type"],
            address=validated_data["address"],
            city=validated_data["city"],
            country=validated_data["country"],
            phone=validated_data["phone"],
            email=validated_data["email"],
            website=validated_data.get("website", ""),
            schooladmin=user,
        )

        # Create SchoolAdmin profile
        SchoolAdmin.objects.create(user=user, school=school, is_primary=True)

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
