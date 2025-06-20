from django.test import TestCase
from rest_framework.exceptions import ValidationError
from skul_data.users.serializers.school_admin import (
    AdministratorProfileSerializer,
    AdministratorProfileCreateSerializer,
    AdministratorProfileUpdateSerializer,
)
from skul_data.users.models.base_user import User
from skul_data.users.models.school_admin import AdministratorProfile
from skul_data.tests.users_tests.test_helpers_admins import create_test_school


class AdministratorProfileSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.user = User.objects.create_user(
            email="admin@test.com",
            username="testadmin",
            password="testpass",
            first_name="Admin",
            last_name="User",
            user_type=User.ADMINISTRATOR,
        )
        self.admin_profile = AdministratorProfile.objects.create(
            user=self.user,
            school=self.school,
            position="Principal",
            access_level="elevated",
        )

    def test_administrator_profile_serializer(self):
        serializer = AdministratorProfileSerializer(self.admin_profile)
        data = serializer.data

        self.assertEqual(data["username"], self.user.username)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["first_name"], self.user.first_name)
        self.assertEqual(data["last_name"], self.user.last_name)
        self.assertEqual(data["full_name"], self.user.get_full_name())
        self.assertEqual(data["position"], "Principal")
        self.assertEqual(data["access_level"], "elevated")
        self.assertTrue(data["is_active"])

    def test_administrator_profile_create_serializer(self):
        new_user = User.objects.create_user(
            email="newadmin@test.com",
            username="newadmin",
            password="testpass",
            first_name="New",
            last_name="Admin",
            user_type=User.ADMINISTRATOR,
        )

        data = {
            "user_id": new_user.id,
            "school": self.school.id,
            "position": "Deputy Principal",
            "access_level": "standard",
            "permissions_granted": ["manage_users", "view_analytics"],
            "notes": "Test notes",
        }

        serializer = AdministratorProfileCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        admin_profile = serializer.save()

        self.assertEqual(admin_profile.user, new_user)
        self.assertEqual(admin_profile.school, self.school)
        self.assertEqual(admin_profile.position, "Deputy Principal")
        self.assertEqual(admin_profile.access_level, "standard")
        self.assertEqual(
            admin_profile.permissions_granted, ["manage_users", "view_analytics"]
        )

    def test_administrator_profile_create_serializer_invalid_user(self):
        # Test with user who is already an administrator
        data = {
            "user_id": self.user.id,
            "school": self.school.id,
            "position": "Deputy Principal",
        }

        serializer = AdministratorProfileCreateSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_administrator_profile_update_serializer(self):
        data = {
            "position": "Senior Administrator",
            "access_level": "elevated",
            "permissions_granted": ["manage_users", "manage_teachers"],
            "is_active": False,
            "notes": "Updated notes",
        }

        serializer = AdministratorProfileUpdateSerializer(
            instance=self.admin_profile, data=data, partial=True
        )
        self.assertTrue(serializer.is_valid())
        admin_profile = serializer.save()

        self.assertEqual(admin_profile.position, "Senior Administrator")
        self.assertEqual(admin_profile.access_level, "elevated")
        self.assertEqual(
            admin_profile.permissions_granted, ["manage_users", "manage_teachers"]
        )
        self.assertFalse(admin_profile.is_active)


# python manage.py test skul_data.tests.users_tests.test_admins_serializers
