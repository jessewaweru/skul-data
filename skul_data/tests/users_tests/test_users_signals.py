from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.users.models.role import Role, Permission
from skul_data.tests.users_tests.users_roles_factories import (
    RoleFactory,
    PermissionFactory,
    SchoolAdminUserFactory,
    SchoolFactory,
)
from skul_data.users.models.base_user import User


class RolePermissionSignalTests(TestCase):
    """Test signals for role and permission actions"""

    def setUp(self):
        # Enable test mode for action logging
        from skul_data.action_logs.utils.action_log import set_test_mode

        set_test_mode(True)

        # Create a school first
        self.school = SchoolFactory()

        # Create an admin user associated with the school
        self.admin = self.school.schooladmin
        User.set_current_user(self.admin)  # Set user context for signals

        # Test data
        self.role = RoleFactory(name="Test Role", school=self.school)
        self.permission = PermissionFactory(code="test_permission")

    def tearDown(self):
        from skul_data.action_logs.utils.action_log import set_test_mode

        set_test_mode(False)
        User.set_current_user(None)

    def test_role_creation_log(self):
        """Test that role creation triggers an action log"""
        print("Before role creation - current user:", User.get_current_user())
        new_role = RoleFactory(name="New Role")
        print("After role creation")

        logs = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Role),
            object_id=new_role.id,
            category=ActionCategory.CREATE,
        )
        print("Logs found:", logs.count())
        for log in logs:
            print("Log:", log.action, "User:", log.user)

        log = logs.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, "Created role")
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.metadata["name"], "New Role")

    def test_role_update_log(self):
        """Test that role updates are logged"""
        self.role.name = "Updated Role"
        self.role.save()

        log = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Role),
            object_id=self.role.id,
            category=ActionCategory.UPDATE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.action, "Updated role")
        self.assertEqual(log.metadata["name"], "Updated Role")

    def test_role_deletion_log(self):
        """Test that role deletion is logged"""
        role_id = self.role.id
        self.role.delete()

        log = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Role),
            object_id=role_id,
            category=ActionCategory.DELETE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.action, "Deleted Role")  # Uppercase 'R' to match signal
        self.assertEqual(log.metadata["name"], "Test Role")  # Now included in metadata

    def test_permission_creation_log(self):
        """Test permission creation logging"""
        new_perm = PermissionFactory(code="new_perm")

        log = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Permission),
            object_id=new_perm.id,
            category=ActionCategory.CREATE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.action, "Created permission")
        self.assertEqual(log.metadata["code"], "new_perm")

    def test_permission_assignment_log(self):
        """Test adding permissions to a role"""
        self.role.permissions.add(self.permission)

        log = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Role),
            object_id=self.role.id,
            category=ActionCategory.UPDATE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.action, "Added permissions to role Test Role")
        self.assertIn(self.permission.code, log.metadata["affected_permissions"])

    def test_permission_removal_log(self):
        """Test removing permissions from a role"""
        self.role.permissions.add(self.permission)
        self.role.permissions.remove(self.permission)

        logs = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Role),
            object_id=self.role.id,
            category=ActionCategory.UPDATE,
        ).order_by("-timestamp")

        # Should have both add and remove logs
        self.assertEqual(logs.count(), 2)
        remove_log = logs.first()
        self.assertEqual(remove_log.action, "Removed permissions from role Test Role")
        self.assertIn(self.permission.code, remove_log.metadata["affected_permissions"])

    def test_bulk_permission_clear_log(self):
        """Test clearing all permissions from a role"""
        self.role.permissions.add(self.permission, PermissionFactory())
        self.role.permissions.clear()

        log = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Role),
            object_id=self.role.id,
            category=ActionCategory.UPDATE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.action, "Cleared all permissions from role Test Role")
        self.assertEqual(log.metadata["total_permissions"], 0)

    def test_anonymous_action_attribution(self):
        """Test actions without a user context"""
        User.set_current_user(None)  # Clear user context
        role = RoleFactory(name="No Owner Role")

        log = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Role), object_id=role.id
        ).first()

        self.assertIsNotNone(log)
        self.assertIsNone(log.user)  # Should still log but with no user


# python manage.py test skul_data.tests.users_tests.test_users_signals
