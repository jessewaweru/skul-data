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
            "is_administrator",
            "last_login",
        ]
        read_only_fields = ["id", "user_tag", "is_staff"]


class UserDetailSerializer(BaseUserSerializer):
    """Enhanced UserDetailSerializer with school information for all user types"""

    teacher_profile = serializers.SerializerMethodField()
    parent_profile = serializers.SerializerMethodField()
    school_admin_profile = serializers.SerializerMethodField()
    sessions = serializers.SerializerMethodField()
    school_id = serializers.SerializerMethodField()
    school = (
        serializers.SerializerMethodField()
    )  # ← KEY FIX: Add this as SerializerMethodField
    is_administrator = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(
        read_only=True
    )  # Fixed: removed incorrect source
    status = serializers.SerializerMethodField()

    class Meta(BaseUserSerializer.Meta):
        fields = BaseUserSerializer.Meta.fields + [
            "teacher_profile",
            "parent_profile",
            "sessions",
            "school_id",
            "school_admin_profile",
            "school",  # Include in fields list
            "is_administrator",
            "last_login",
            "status",
        ]

    def get_teacher_profile(self, obj):
        """Get teacher profile information"""
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
        """Get parent profile information"""
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

    def get_school_admin_profile(self, obj):
        """Get school admin profile information"""
        if hasattr(obj, "school_admin_profile"):
            profile = obj.school_admin_profile
            return {
                "id": profile.id,
                "school": (
                    {
                        "id": profile.school.id,
                        "name": profile.school.name,
                        "code": profile.school.code,
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
        """Get user session information"""
        if hasattr(obj, "sessions"):
            return [
                {
                    "session_key": us.session.session_key,
                    "ip_address": us.ip_address,
                    "device": us.device,
                }
                for us in obj.sessions.all()
            ]
        return []

    def get_school_id(self, obj):
        """
        Get school ID from any profile type.
        Priority: school_admin_profile > teacher_profile > parent_profile > role
        """
        # Try school_admin_profile first
        if hasattr(obj, "school_admin_profile") and obj.school_admin_profile.school:
            return obj.school_admin_profile.school.id

        # Try teacher_profile
        if hasattr(obj, "teacher_profile") and obj.teacher_profile.school:
            return obj.teacher_profile.school.id

        # Try parent_profile
        if hasattr(obj, "parent_profile") and obj.parent_profile.school:
            return obj.parent_profile.school.id

        # Try role
        if hasattr(obj, "role") and obj.role and hasattr(obj.role, "school"):
            return obj.role.school.id

        return None

    def get_school(self, obj):
        """
        ★ KEY FIX ★
        Get complete school information from any profile type.
        This ensures ALL users (admin, teacher, parent) get their school data.
        Priority: school_admin_profile > teacher_profile > parent_profile > role
        """
        # Try school_admin_profile first
        if hasattr(obj, "school_admin_profile") and obj.school_admin_profile.school:
            school = obj.school_admin_profile.school
            return {
                "id": school.id,
                "name": school.name,
                "code": school.code,
            }

        # Try teacher_profile
        if hasattr(obj, "teacher_profile") and obj.teacher_profile.school:
            school = obj.teacher_profile.school
            return {
                "id": school.id,
                "name": school.name,
                "code": school.code,
            }

        # Try parent_profile
        if hasattr(obj, "parent_profile") and obj.parent_profile.school:
            school = obj.parent_profile.school
            return {
                "id": school.id,
                "name": school.name,
                "code": school.code,
            }

        # Try role (if exists)
        if hasattr(obj, "role") and obj.role and hasattr(obj.role, "school"):
            school = obj.role.school
            return {
                "id": school.id,
                "name": school.name,
                "code": school.code,
            }

        return None

    def get_is_administrator(self, obj):
        """Check if user has administrator privileges"""
        return obj.is_administrator or obj.user_type == User.ADMINISTRATOR

    def get_status(self, obj):
        """Get user status as string"""
        return "Active" if obj.is_active else "Inactive"
