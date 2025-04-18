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


# === PREDEFINED PERMISSIONS FOR REFERENCE ===

# These are just constants to keep things organized; they should match the values saved in Role.permissions
# You can import and reuse them in your views for clarity

# --- Teacher Permissions ---
VIEW_OWN_STUDENTS = "view_own_students"
VIEW_OWN_PARENTS = "view_own_parents"
CREATE_OWN_REPORTS = "create_own_reports"
VIEW_OWN_REPORTS = "view_own_reports"
VIEW_CALENDAR = "view_calendar"

# --- Admin Permissions ---
ACCESS_ALL = "access_all"

# --- Parent Permissions ---
VIEW_OWN_CHILDREN = "view_own_children"
VIEW_CHILD_CLASS_PERFORMANCE = "view_child_class_performance"
VIEW_EVENTS = "view_events"
