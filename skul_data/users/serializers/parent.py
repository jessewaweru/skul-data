from rest_framework import serializers, status
from skul_data.users.models.parent import Parent, ParentNotification, ParentStatusChange
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from skul_data.students.models.student import Student
from django.utils.crypto import get_random_string
from skul_data.users.serializers.base_user import BaseUserSerializer
from skul_data.schools.models.school import School
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory

User = get_user_model()


class ParentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    children = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(), many=True, required=False
    )
    # children_details = StudentSerializer(many=True, read_only=True, source="children")
    children_details = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)

    class Meta:
        model = Parent
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "school",
            "children",
            "children_details",
            "address",
            "occupation",
            "status",
            "preferred_language",
            "receive_email_notifications",
            "last_login",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_children_details(self, obj):
        from skul_data.students.serializers.student import SimpleStudentSerializer

        return SimpleStudentSerializer(
            obj.children.all(),
            many=True,
            context=self.context,  # Pass context if needed for request or other data
        ).data

    def validate_school(self, value):
        """Ensure the school matches the requesting user's school"""
        user = self.context["request"].user
        if not user.user_type == User.SCHOOL_ADMIN and value != user.school:
            raise serializers.ValidationError("Invalid school for this user")
        return value


class ParentCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, required=False)
    school = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(), write_only=True
    )

    class Meta:
        model = Parent
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "password",
            "phone_number",
            "school",
            "address",
            "occupation",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        request = self.context.get("request")
        email = validated_data.get("email")

        # Create the User first
        user_data = {
            "email": validated_data.pop("email", email),
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "username": email,
            "user_type": User.PARENT,
        }

        if "password" in validated_data:
            user_data["password"] = make_password(validated_data.pop("password"))
        else:
            user_data["password"] = make_password(get_random_string(12))

        user = User.objects.create(**user_data)

        # Set current user for the signal to pick up
        if request and request.user:
            User.set_current_user(request.user)

        # Then create the Parent profile - let log_model_save signal handle logging
        parent = Parent.objects.create(user=user, **validated_data)

        return parent

    def to_representation(self, instance):
        return ParentSerializer(instance, context=self.context).data


class ParentChildAssignmentSerializer(serializers.Serializer):
    student_ids = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(), many=True
    )
    action = serializers.ChoiceField(choices=["ADD", "REMOVE", "REPLACE"])


class ParentNotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = [
            "receive_email_notifications",
            "preferred_language",
        ]


class ParentNotificationSerializer(serializers.ModelSerializer):
    sent_by = BaseUserSerializer(read_only=True)
    related_student = serializers.SerializerMethodField()

    class Meta:
        model = ParentNotification
        fields = "__all__"
        read_only_fields = ["created_at"]

    def get_related_student(self, obj):
        # Import inside method to avoid circular dependency
        from skul_data.students.serializers.student import StudentSerializer

        if obj.related_student:
            return StudentSerializer(obj.related_student).data
        return None


class ParentStatusChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentStatusChange
        fields = [
            "id",
            "parent",
            "changed_by",
            "from_status",
            "to_status",
            "reason",
            "changed_at",
        ]
        read_only_fields = ["changed_at"]


class ParentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Parent.STATUS_CHOICES)
    reason = serializers.CharField(required=False, allow_blank=True)
