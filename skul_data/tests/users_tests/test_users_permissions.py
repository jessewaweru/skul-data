from django.test import TestCase, RequestFactory
from skul_data.tests.users_tests.users_factories import (
    SchoolFactory,
    RoleFactory,
    PermissionFactory,
    ParentFactory,
    TeacherFactory,
    SchoolAdminFactory,
    UserFactory,
)
from skul_data.users.permissions.permission import (
    IsSchoolAdmin,
    IsPrimaryAdmin,
    IsAdministrator,
    IsTeacher,
    IsParent,
    HasRolePermission,
)
from skul_data.users.models.base_user import User


class PermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.school = SchoolFactory()
        self.role = RoleFactory(school=self.school)
        self.permission = PermissionFactory(
            code="test_perm"
        )  # Changed from codename to code

    def test_is_school_admin_permission(self):
        permission = IsSchoolAdmin()
        admin = SchoolAdminFactory(school=self.school)
        request = self.factory.get("/")
        request.user = admin.user

        self.assertTrue(permission.has_permission(request, None))

    def test_is_primary_admin_permission(self):
        permission = IsPrimaryAdmin()
        primary_admin = SchoolAdminFactory(school=self.school, is_primary=True)
        non_primary_admin = SchoolAdminFactory(school=self.school, is_primary=False)

        request = self.factory.get("/")
        request.user = primary_admin.user
        self.assertTrue(permission.has_permission(request, None))

        request.user = non_primary_admin.user
        self.assertFalse(permission.has_permission(request, None))

    def test_is_administrator_permission(self):
        permission = IsAdministrator()
        admin = SchoolAdminFactory(school=self.school)
        admin.user.user_type = "administrator"
        admin.user.save()

        request = self.factory.get("/")
        request.user = admin.user
        self.assertTrue(permission.has_permission(request, None))

    def test_is_teacher_permission(self):
        permission = IsTeacher()
        teacher = TeacherFactory(school=self.school)

        request = self.factory.get("/")
        request.user = teacher.user
        self.assertTrue(permission.has_permission(request, None))

    def test_is_parent_permission(self):
        permission = IsParent()
        parent = ParentFactory(school=self.school)

        request = self.factory.get("/")
        request.user = parent.user
        self.assertTrue(permission.has_permission(request, None))

    def test_has_role_permission(self):
        permission = HasRolePermission()

        # Use a regular User instead of SchoolAdmin to avoid permissions bypass
        regular_user = UserFactory()
        regular_user.role = self.role
        regular_user.is_staff = False
        regular_user.user_type = "regular"  # Not an admin
        regular_user.save()

        self.role.permissions.add(self.permission)

        request = self.factory.get("/")
        request.user = regular_user

        # Test with view that has required_permission
        class TestView:
            required_permission = "test_perm"

        self.assertTrue(permission.has_permission(request, TestView()))

        # Test with view that has different required_permission
        class InvalidView:
            required_permission = "invalid_perm"

        self.assertFalse(permission.has_permission(request, InvalidView()))

        # Now test with school admin - should bypass permission check
        admin_user = SchoolAdminFactory(school=self.school).user
        admin_user.user_type = User.SCHOOL_ADMIN
        admin_user.save()

        request.user = admin_user
        self.assertTrue(permission.has_permission(request, InvalidView()))


# python manage.py test skul_data.tests.users_tests.test_users_permissions
