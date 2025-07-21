from rest_framework.permissions import BasePermission, SAFE_METHODS
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher

# === BROAD ROLE CHECKS ===


class IsSchoolAdmin(BasePermission):
    """Only for the primary school owner (SchoolAdmin)"""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == User.SCHOOL_ADMIN
            and hasattr(request.user, "school_admin_profile")
            and request.user.school_admin_profile.is_primary
        )


class IsPrimaryAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.school_admin_profile.is_primary
        )


class IsAdministrator(BasePermission):
    """For both standalone administrators and teacher-administrators"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Administrator users
        if request.user.user_type == User.ADMINISTRATOR:
            return True

        # Teacher administrators
        if request.user.user_type == User.TEACHER:
            try:
                return request.user.teacher_profile.is_administrator
            except Teacher.DoesNotExist:
                return False

        return False


class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == User.TEACHER


class IsParent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == User.PARENT


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
        print(f"Checking permission for {request.user}")
        user = request.user

        if not user.is_authenticated:
            return False

        # 1. School owners (primary admins) have all permissions
        if (
            user.user_type == User.SCHOOL_ADMIN
            and hasattr(user, "school_admin_profile")
            and user.school_admin_profile.is_primary
        ):
            return True

        required_permission = self._get_required_permission(view, request.method)
        if not required_permission:
            return False

        # 2. Administrator permissions (both standalone and teacher-administrators)
        if user.user_type == User.ADMINISTRATOR or (
            user.user_type == User.TEACHER
            and hasattr(user, "teacher_profile")
            and user.teacher_profile.is_administrator
        ):
            # Check administrator_profile permissions first
            if hasattr(user, "administrator_profile"):
                if required_permission in getattr(
                    user.administrator_profile, "permissions_granted", []
                ):
                    return True

            # Then check role permissions
            if hasattr(user, "role") and user.role:
                if user.role.permissions.filter(code=required_permission).exists():
                    return True

        # 3. Special cases (keep your existing special handling)
        if (
            hasattr(view, "action")
            and view.action == "mark_attendance"
            and user.user_type == User.TEACHER
        ):
            return True

        if request.method == "GET":
            view_action = getattr(view, "action", None)
            if view_action == "retrieve":
                if user.user_type in [User.PARENT, User.TEACHER]:
                    return True
            elif view_action == "list":
                if user.user_type in [User.PARENT, User.TEACHER]:
                    return True

        # 4. Standard role permission check (for non-administrators)
        if hasattr(user, "role") and user.role:
            return user.role.permissions.filter(code=required_permission).exists()

        return False

    def _get_required_permission(self, view, method):
        """Helper to get the required permission from the view"""
        # First check for method-specific permissions
        method_permission_attr = f"required_permission_{method.lower()}"
        if hasattr(view, method_permission_attr):
            return getattr(view, method_permission_attr)

        # Fall back to general permission if method-specific not found
        return getattr(view, "required_permission", None)

    def _check_required_permission(self, view, method, permission_codes):
        """Helper to check if permission exists in given list"""
        required_permission = self._get_required_permission(view, method)
        if not required_permission:
            return False
        return required_permission in permission_codes

    def has_object_permission(self, request, view, obj):
        user = request.user

        # 1. School owners (primary admins) have all permissions
        if (
            user.user_type == User.SCHOOL_ADMIN
            and hasattr(user, "school_admin_profile")
            and user.school_admin_profile.is_primary
        ):
            return True

        # 2. Administrator object-level permissions
        if user.user_type == User.ADMINISTRATOR or (
            user.user_type == User.TEACHER
            and hasattr(user, "teacher_profile")
            and user.teacher_profile.is_administrator
        ):
            # Check administrator-specific permissions first
            if hasattr(user, "administrator_profile"):
                admin_profile = user.administrator_profile
                if hasattr(
                    admin_profile, "permissions_granted"
                ) and self._check_required_permission(
                    view, request.method, admin_profile.permissions_granted
                ):
                    return True

        # 3. Special cases (keep your existing special handling)
        # Attendance objects - safely check for action attribute
        if (
            hasattr(view, "action")
            and view.action == "mark_attendance"
            and user.user_type == User.TEACHER
        ):
            if hasattr(obj, "school_class"):
                return obj.school_class.class_teacher == user.teacher_profile

        # Owner check
        owner_field = getattr(view, "owner_field", "user")
        if hasattr(obj, owner_field) and getattr(obj, owner_field) == user:
            return True

        # Parent viewing own profile - safely check for action attribute
        view_action = getattr(view, "action", None)
        if user.user_type == User.PARENT and view_action == "retrieve":
            return obj.user == user

        # 4. General permission check
        return self.has_permission(request, view)


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

# --- Fees Management Permissions ---
MANAGE_FEES = "manage_fees"
VIEW_FEES = "view_fees"
GENERATE_FEE_REPORTS = "generate_fee_reports"
SEND_FEE_REMINDERS = "send_fee_reminders"

# Recommended permission set for initial setup
DEFAULT_PERMISSIONS = [
    (CREATE_EVENTS, "Can create calendar events"),
    (MANAGE_EVENTS, "Can manage all calendar events"),
    (VIEW_CALENDAR, "Can view the school calendar"),
    (EXPORT_CALENDAR, "Can export calendar data"),
    (MANAGE_FEES, "Can manage school fees"),
    (VIEW_FEES, "Can view fee records"),
    (GENERATE_FEE_REPORTS, "Can generate fee reports"),
    (SEND_FEE_REMINDERS, "Can send fee reminders"),
]

SCHOOL_ADMIN_PERMISSIONS = [
    ("manage_school", "Manage school settings"),
    ("manage_users", "Create/manage school users"),
    ("manage_academics", "Manage academic structure"),
    ("view_reports", "View all school reports"),
]
# Additional permissions for timetables
VIEW_TIMETABLES = "view_timetables"
MANAGE_TIMETABLES = "manage_timetables"
GENERATE_TIMETABLES = "generate_timetables"
VIEW_TEACHER_TIMETABLES = "view_teacher_timetables"
VIEW_TIMETABLE_SETTINGS = "view_timetable_settings"
MANAGE_TIMETABLE_SETTINGS = "manage_timetable_settings"

DEFAULT_TIMETABLE_PERMISSIONS = [
    (VIEW_TIMETABLES, "Can view school timetables"),
    (MANAGE_TIMETABLES, "Can create and edit timetables"),
    (GENERATE_TIMETABLES, "Can generate timetables automatically"),
    (VIEW_TEACHER_TIMETABLES, "Can view teacher timetables"),
    (VIEW_TIMETABLE_SETTINGS, "Can view timetable settings and structures"),
    (MANAGE_TIMETABLE_SETTINGS, "Can manage timetable settings and structures"),
]
