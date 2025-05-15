from rest_framework.permissions import BasePermission, SAFE_METHODS
from skul_data.users.models.base_user import User

# === BROAD ROLE CHECKS ===


# New permission classes
class IsSchoolAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == User.SCHOOL_ADMIN
        )


class IsPrimaryAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.school_admin_profile.is_primary
        )


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == User.SCHOOL_ADMIN
            and request.user.is_staff
        )


class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "teacher"


class IsParent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "parent"


class CanCreateEvent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.user_type == User.SCHOOL_ADMIN
            or request.user.role.permissions.filter(code="create_events").exists()
        )


class CanManageEvent(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return (
            request.user.is_authenticated
            and request.user.user_type == User.SCHOOL_ADMIN
        )

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        # School admins always have permission
        if request.user.user_type == User.SCHOOL_ADMIN:
            return True

        # Check if user created the event
        if hasattr(obj, "created_by") and obj.created_by == request.user:
            return True

        # Check role permissions if role exists
        if hasattr(request.user, "role") and request.user.role:
            return request.user.role.permissions.filter(code="manage_events").exists()

        # Default deny
        return False


# === FLEXIBLE, DYNAMIC PERMISSION CHECK ===


class HasRolePermission(BasePermission):
    """
    This permission checks if a user's role (via Role model) has a specific permission key.
    The view should define required permissions in these formats:

    - required_permission = 'view_calendar'  # For all methods
    - required_permission_get = 'view_calendar'  # For GET only
    - required_permission_post = 'create_calendar'  # For POST only
    etc.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        # Staff and school admins always have permission
        if user.is_staff or user.user_type == User.SCHOOL_ADMIN:
            return True

        # Allow parents to view their own profile
        if request.method == "GET" and view.action == "retrieve":
            if user.user_type == User.PARENT:
                return True

        # Allow teachers to view their own profile
        if request.method == "GET" and view.action == "retrieve":
            if request.user.user_type == User.TEACHER:
                return True

        # Primary school admin check
        if (
            hasattr(user, "school_admin_profile")
            and user.school_admin_profile.is_primary
        ):
            return True

        # Get the required permission from the view
        # First check for method-specific permissions
        method = request.method.lower()
        method_permission = getattr(view, f"required_permission_{method}", None)

        # Fall back to general permission if method-specific not found
        required_permission = method_permission or getattr(
            view, "required_permission", None
        )

        if not required_permission:
            return False  # No permission defined = deny by default

        # No role means no permissions
        role = getattr(user, "role", None)
        if not role:
            return False

        # Check if the required permission is in the role's permissions
        return role.permissions.filter(code=required_permission).exists()

    # def has_object_permission(self, request, view, obj):
    #     # For object-level permissions
    #     # Staff and school admins always have permission
    #     if request.user.is_staff or request.user.user_type == User.SCHOOL_ADMIN:
    #         return True

    #     # Primary school admin check
    #     if (
    #         hasattr(request.user, "school_admin_profile")
    #         and request.user.school_admin_profile.is_primary
    #     ):
    #         return True

    #     # Reuse the same logic but also check for owner if applicable
    #     has_general_permission = self.has_permission(request, view)

    #     # If general permission passes, also check ownership if relevant
    #     if has_general_permission:
    #         # If the object has a user field and it matches the requester
    #         owner_field = getattr(view, "owner_field", "user")
    #         if hasattr(obj, owner_field) and getattr(obj, owner_field) == request.user:
    #             return True

    #         # If the object has a created_by field and it matches the requester
    #         if hasattr(obj, "created_by") and obj.created_by == request.user:
    #             return True

    #         # Specific school check if relevant
    #         if (
    #             hasattr(obj, "school")
    #             and hasattr(request.user, "school")
    #             and obj.school == request.user.school
    #         ):
    #             return True

    #     return has_general_permission

    def has_object_permission(self, request, view, obj):
        # Staff and school admins always have permission
        if request.user.is_staff or request.user.user_type == User.SCHOOL_ADMIN:
            return True

        # Primary school admin check
        if (
            hasattr(request.user, "school_admin_profile")
            and request.user.school_admin_profile.is_primary
        ):
            return True

        # Check if the user is the owner of the object
        owner_field = getattr(view, "owner_field", "user")
        if hasattr(obj, owner_field) and getattr(obj, owner_field) == request.user:
            return True

        # For parents trying to view their own profile
        if request.user.user_type == User.PARENT and view.action == "retrieve":
            return obj.user == request.user

        # Check general permission (role-based)
        has_general_permission = self.has_permission(request, view)

        # For teachers, they should only be able to view their own profile
        if request.user.user_type == User.TEACHER:
            return False  # If they got here, it's not their profile

        return has_general_permission


# # === PREDEFINED PERMISSIONS FOR REFERENCE ===

# # These are just constants to keep things organized; they should match the values saved in Role.permissions
# # You can import and reuse them in your views for clarity

# # --- Teacher Permissions ---
# VIEW_OWN_STUDENTS = "view_own_students"
# VIEW_OWN_PARENTS = "view_own_parents"
# CREATE_OWN_REPORTS = "create_own_reports"
# VIEW_OWN_REPORTS = "view_own_reports"
# VIEW_CALENDAR = "view_calendar"

# # --- Admin Permissions ---
# ACCESS_ALL = "access_all"

# # --- Parent Permissions ---
# VIEW_OWN_CHILDREN = "view_own_children"
# VIEW_CHILD_CLASS_PERFORMANCE = "view_child_class_performance"
# VIEW_EVENTS = "view_events"

# # --- School Class Permissions ---
# MANAGE_CLASSES = "manage_classes"
# VIEW_CLASSES = "view_classes"
# MANAGE_CLASS_DOCUMENTS = "manage_class_documents"
# VIEW_CLASS_DOCUMENTS = "view_class_documents"
# MANAGE_ATTENDANCE = "manage_attendance"
# VIEW_ATTENDANCE = "view_attendance"

# # --- Teacher Permissions ---
# VIEW_TEACHER_PROFILE = "view_teacher_profile"
# MANAGE_TEACHERS = "manage_teachers"
# VIEW_TEACHER_ATTENDANCE = "view_teacher_attendance"
# MANAGE_TEACHER_ATTENDANCE = "manage_teacher_attendance"
# VIEW_TEACHER_DOCUMENTS = "view_teacher_documents"
# MANAGE_TEACHER_DOCUMENTS = "manage_teacher_documents"
# VIEW_TEACHER_WORKLOAD = "view_teacher_workload"
# MANAGE_TEACHER_WORKLOAD = "manage_teacher_workload"


# === PERMISSION CONSTANTS (For Role model) ===
# These constants should match the codes stored in your Role.permissions

# --- Core Permissions ---
ACCESS_ALL = "access_all"

# --- Calendar/Scheduler Permissions ---
CREATE_EVENTS = "create_events"
MANAGE_EVENTS = "manage_events"
VIEW_CALENDAR = "view_calendar"
EXPORT_CALENDAR = "export_calendar"

# --- Teacher Permissions ---
VIEW_OWN_STUDENTS = "view_own_students"
VIEW_OWN_PARENTS = "view_own_parents"
CREATE_OWN_REPORTS = "create_own_reports"
VIEW_OWN_REPORTS = "view_own_reports"

# --- Parent Permissions ---
VIEW_OWN_CHILDREN = "view_own_children"
VIEW_CHILD_CLASS_PERFORMANCE = "view_child_class_performance"

# --- Class Management Permissions ---
MANAGE_CLASSES = "manage_classes"
VIEW_CLASSES = "view_classes"
MANAGE_CLASS_DOCUMENTS = "manage_class_documents"
VIEW_CLASS_DOCUMENTS = "view_class_documents"
VIEW_CLASS_TIMETABLES = "view_class_timetables"
MANAGE_CLASS_TIMETABLES = "manage_class_timetables"
MANAGE_ATTENDANCE = "manage_attendance"
VIEW_ATTENDANCE = "view_attendance"

# --- Teacher Management Permissions ---
VIEW_TEACHER_PROFILE = "view_teacher_profile"
MANAGE_TEACHERS = "manage_teachers"
VIEW_TEACHER_ATTENDANCE = "view_teacher_attendance"
MANAGE_TEACHER_ATTENDANCE = "manage_teacher_attendance"
VIEW_TEACHER_DOCUMENTS = "view_teacher_documents"
MANAGE_TEACHER_DOCUMENTS = "manage_teacher_documents"
VIEW_TEACHER_WORKLOAD = "view_teacher_workload"
MANAGE_TEACHER_WORKLOAD = "manage_teacher_workload"

# Recommended permission set for initial setup
DEFAULT_PERMISSIONS = [
    (CREATE_EVENTS, "Can create calendar events"),
    (MANAGE_EVENTS, "Can manage all calendar events"),
    (VIEW_CALENDAR, "Can view the school calendar"),
    (EXPORT_CALENDAR, "Can export calendar data"),
]

SCHOOL_ADMIN_PERMISSIONS = [
    ("manage_school", "Manage school settings"),
    ("manage_users", "Create/manage school users"),
    ("manage_academics", "Manage academic structure"),
    ("view_reports", "View all school reports"),
]
