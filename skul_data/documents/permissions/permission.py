from rest_framework.permissions import BasePermission
from skul_data.users.models.base_user import User


class CanUploadDocument(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.user_type in [
            User.SCHOOL_ADMIN,
            User.TEACHER,
        ]


class CanViewDocument(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user

        # School admins can view all documents in their school
        if user.user_type == User.SCHOOL_ADMIN:
            return user.school_admin_profile.school == obj.school

        # Teachers can view documents for their school/classes
        if user.user_type == User.TEACHER:
            teacher_profile = user.teacher_profile
            if teacher_profile.school != obj.school:
                return False

            # If document is associated with a class, check if teacher teaches that class
            if (
                obj.related_class
                and obj.related_class != teacher_profile.assigned_class
            ):
                return False

            return True

        # Parents can view documents for their children
        if user.user_type == User.PARENT:
            parent_profile = user.parent_profile
            if obj.school != parent_profile.school:
                return False

            # Check if document is associated with any of their children
            if obj.related_students.filter(parents=parent_profile).exists():
                return True

            return obj.is_public

        return False


class CanManageDocument(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user

        # Only the uploader or school admin can manage
        return obj.uploaded_by == user or (
            user.user_type == User.SCHOOL_ADMIN
            and user.school_admin_profile.school == obj.school
        )
