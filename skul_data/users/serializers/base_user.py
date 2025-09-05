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
            "first_name",
            "last_name",
            "user_type",
            "user_tag",
            "is_active",
            "is_staff",
            "role",
            "role_id",
            "is_administrator",  # Add this
            "last_login",  # Add this
        ]
        read_only_fields = ["id", "user_tag", "is_staff"]


class UserDetailSerializer(BaseUserSerializer):
    teacher_profile = serializers.SerializerMethodField()
    parent_profile = serializers.SerializerMethodField()
    school_admin_profile = (
        serializers.SerializerMethodField()
    )  # Changed from schooladmin_profile to match your model
    sessions = serializers.SerializerMethodField()  # Add this for user sessions
    school_id = serializers.SerializerMethodField()
    is_administrator = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta(BaseUserSerializer.Meta):
        fields = BaseUserSerializer.Meta.fields + [
            "teacher_profile",
            "parent_profile",
            "sessions",
            "school_id",
            "school_admin_profile",
            "school",
            "is_administrator",
            "last_login",
            "status",
        ]

    def get_teacher_profile(self, obj):
        if hasattr(obj, "teacher_profile"):
            return {
                "school": (
                    str(obj.teacher_profile.school)
                    if obj.teacher_profile.school
                    else None
                ),
                "subjects_taught": (
                    [
                        str(subject)
                        for subject in obj.teacher_profile.subjects_taught.all()
                    ]
                    if hasattr(obj.teacher_profile, "subjects_taught")
                    else []
                ),
                "assigned_classes": (
                    [str(cls) for cls in obj.teacher_profile.assigned_classes.all()]
                    if hasattr(obj.teacher_profile, "assigned_classes")
                    else []
                ),
                "status": obj.teacher_profile.status,
            }
        return None

    def get_parent_profile(self, obj):
        if hasattr(obj, "parent_profile"):
            return {
                "school": (
                    str(obj.parent_profile.school.id)
                    if obj.parent_profile.school
                    else None
                ),
                "phone_number": obj.parent_profile.phone_number,
                "children": [
                    {"id": child.id, "name": str(child)}
                    for child in obj.parent_profile.children.all()
                ],
                "status": obj.parent_profile.status,
            }
        return None

    # def get_school_admin_profile(self, obj):
    #     if hasattr(obj, "school_admin_profile"):
    #         return {
    #             "school": (
    #                 str(obj.school_admin_profile.school.id)
    #                 if obj.school_admin_profile.school
    #                 else None
    #             ),
    #             "is_primary": obj.school_admin_profile.is_primary,
    #         }
    #     return None

    # In your UserDetailSerializer

    def get_school_admin_profile(self, obj):
        if hasattr(obj, "school_admin_profile"):
            profile = obj.school_admin_profile
            return {
                "id": profile.id,
                "school": (
                    {
                        "id": profile.school.id,
                        "name": profile.school.name,
                        "code": profile.school.code,  # Add if needed
                    }
                    if profile.school
                    else None
                ),
                "is_primary": profile.is_primary,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }
        return None

    def get_sessions(self, obj):
        if hasattr(obj, "sessions"):
            return [
                {
                    "session_key": us.session.session_key,  # Access through session relation
                    "ip_address": us.ip_address,
                    "device": us.device,
                }
                for us in obj.sessions.all()  # This gets UserSession objects
            ]
        return []

    def get_school_id(self, obj):
        """Directly get school ID from admin profile"""
        if hasattr(obj, "school_admin_profile") and obj.school_admin_profile.school:
            return obj.school_admin_profile.school.id
        return None

    def get_school(self, obj):
        """Get complete school information"""
        if hasattr(obj, "school_admin_profile") and obj.school_admin_profile.school:
            school = obj.school_admin_profile.school
            return {
                "id": school.id,
                "name": school.name,
                "code": school.code,
            }
        return None

    def get_is_administrator(self, obj):
        return obj.is_administrator or obj.user_type == User.ADMINISTRATOR

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"
