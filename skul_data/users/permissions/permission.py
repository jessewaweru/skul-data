from rest_framework.permissions import BasePermission, SAFE_METHODS

# === BROAD ROLE CHECKS ===


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and request.user.user_type == "administrator"
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
            request.user.is_superuser
            or request.user.role.permissions.filter(code="create_events").exists()
        )


class CanManageEvent(BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            request.user.is_superuser
            or obj.created_by == request.user
            or request.user.role.permissions.filter(code="manage_events").exists()
        )


# === FLEXIBLE, DYNAMIC PERMISSION CHECK ===


class HasRolePermission(BasePermission):
    """
    This permission checks if a user's role (via Role model) has a specific permission key.
    The view should define a required_permission attribute like:
        required_permission = 'view_calendar'
    """

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        # Superuser override
        if user.is_superuser:
            return True

        role = getattr(user, "role", None)
        if not role:
            return False

        required_permission = getattr(view, "required_permission", None)
        if not required_permission:
            return False  # No permission key defined on view = deny by default

        return required_permission in role.permissions


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
    # ... keep your existing permissions ...
]
