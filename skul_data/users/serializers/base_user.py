from rest_framework import serializers
from skul_data.users.models.base_user import User
from skul_data.users.models.role import Role
from skul_data.users.serializers.role import RoleSerializer


class BaseUserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source="role", write_only=True, required=False
    )
    user_type = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "user_type",
            "user_tag",
            "is_active",
            "is_staff",
            "role",
            "role_id",
        ]
        read_only_fields = ["id", "user_tag", "is_staff"]


class UserDetailSerializer(BaseUserSerializer):
    teacher_profile = serializers.SerializerMethodField()
    parent_profile = serializers.SerializerMethodField()
    schooladmin_profile = serializers.SerializerMethodField()

    class Meta(BaseUserSerializer.Meta):
        fields = BaseUserSerializer.Meta.fields + [
            "teacher_profile",
            "parent_profile",
            "schooladmin_profile",
        ]

    def get_teacher_profile(self, obj):
        if hasattr(obj, "teacher_profile"):
            return {
                "school": str(obj.teacher_profile.school),
                "subjects_taught": obj.teacher_profile.subjects_taught,
                "assigned_class": (
                    str(obj.teacher_profile.assigned_class)
                    if obj.teacher_profile.assigned_class
                    else None
                ),
            }
        return None

    def get_parent_profile(self, obj):
        if hasattr(obj, "parent_profile"):
            return {
                "school": str(obj.parent_profile.school),
                "phone_number": obj.parent_profile.phone_number,
                "children": [str(child) for child in obj.parent_profile.children.all()],
            }
        return None

    def get_schooladmin_profile(self, obj):
        if hasattr(obj, "schooladmin_profile"):
            return {
                "school_name": obj.schooladmin_profile.school_name,
                "school_code": obj.schooladmin_profile.school_code,
                "phone_number": obj.schooladmin_profile.phone_number,
            }
        return None
