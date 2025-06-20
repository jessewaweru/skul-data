from django.test import TestCase
from django.utils import timezone
from skul_data.users.models.base_user import User
from skul_data.users.models.school_admin import AdministratorProfile
from skul_data.tests.users_tests.test_helpers_admins import (
    create_test_school,
    create_test_teacher,
)


class AdministratorProfileModelTest(TestCase):
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

    def test_administrator_profile_creation(self):
        admin_profile = AdministratorProfile.objects.create(
            user=self.user,
            school=self.school,
            position="Principal",
            access_level="elevated",
        )

        self.assertEqual(admin_profile.user, self.user)
        self.assertEqual(admin_profile.school, self.school)
        self.assertEqual(admin_profile.position, "Principal")
        self.assertEqual(admin_profile.access_level, "elevated")
        self.assertTrue(admin_profile.is_active)

        # Test that user_type is set to ADMINISTRATOR on save
        self.assertEqual(self.user.user_type, User.ADMINISTRATOR)

    def test_administrator_profile_str(self):
        admin_profile = AdministratorProfile.objects.create(
            user=self.user, school=self.school, position="Principal"
        )
        self.assertEqual(str(admin_profile), f"{self.user.get_full_name()} - Principal")

    def test_teacher_as_administrator(self):
        teacher = create_test_teacher(self.school)
        teacher.is_administrator = True
        teacher.administrator_since = timezone.now().date()
        teacher.save()

        self.assertTrue(teacher.is_administrator)
        self.assertEqual(teacher.user.user_type, User.TEACHER)

    def test_access_level_choices(self):
        choices = [choice[0] for choice in AdministratorProfile.ACCESS_LEVEL_CHOICES]
        self.assertListEqual(choices, ["standard", "elevated", "restricted"])


# python manage.py test skul_data.tests.users_tests.test_admins_models
