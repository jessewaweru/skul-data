from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from skul_data.users.models.parent import Parent
from skul_data.users.views.parent import ParentViewSet
from skul_data.tests.parents_tests.test_helpers import (
    create_test_school,
    create_test_parent,
    create_test_role,
)
from skul_data.users.models.school_admin import SchoolAdmin
import random

User = get_user_model()


class ParentPermissionsTest(TestCase):
    def setUp(self):
        # Create a school for testing
        self.school, self.school_admin = create_test_school(
            name=f"Test School {random.randint(1000, 9999)}"
        )

        # Create roles with appropriate permissions
        self.view_only_role = create_test_role(
            school=self.school,
            name=f"View Only Role {random.randint(1000, 9999)}",
            permissions=[
                "view_own_children",
                "view_child_class_performance",
                "view_events",
            ],
        )

        # Create an admin user
        # Note: We're not passing school directly as it's a read-only property
        self.admin_user = User.objects.create_user(
            email="admin@testpermissions.com",
            username="admin_permissions",
            password="testpass",
            user_type=User.SCHOOL_ADMIN,
            is_staff=True,
        )

        # Then create the SchoolAdmin profile to associate with the school
        self.admin_profile = SchoolAdmin.objects.create(
            user=self.admin_user,
            school=self.school,
            is_primary=True,
        )

        # Create parent using helper function, which already creates a user
        self.parent = create_test_parent(
            school=self.school,
            email="parent@testpermissions.com",
        )

        # Get the parent user from the parent profile and assign the role
        self.parent_user = self.parent.user
        self.parent_user.role = self.view_only_role
        self.parent_user.save()

        # Setup the API client
        self.client = APIClient()

    def test_admin_permissions(self):
        # Test that admin users have full permissions
        self.client.force_authenticate(user=self.admin_user)
        # Add your test assertion here
        self.assertTrue(self.admin_user.has_perm("view_own_children"))
        self.assertTrue(self.admin_user.has_perm("manage_events"))

    def test_view_only_permissions(self):
        # Test that parent users with view_only_role have limited permissions
        self.client.force_authenticate(user=self.parent_user)
        # Add your test assertion here
        self.assertTrue(self.parent_user.has_perm("view_own_children"))
        self.assertTrue(self.parent_user.has_perm("view_events"))
        self.assertFalse(self.parent_user.has_perm("manage_events"))

    def test_parent_permissions(self):
        # Test specific parent permissions
        self.client.force_authenticate(user=self.parent_user)
        # Add your test assertion here
        self.assertTrue(self.parent_user.has_perm("view_own_children"))
        self.assertFalse(self.parent_user.has_perm("manage_teachers"))

    def test_custom_action_permissions(self):
        # Test custom action permissions
        self.client.force_authenticate(user=self.parent_user)
        # Add your test assertion here
        self.assertTrue(self.parent_user.has_perm("view_events"))
        self.assertFalse(self.parent_user.has_perm("create_events"))


# python manage.py test skul_data.tests.parents_tests.test_parents_permissions
