from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.users.models.base_user import User
from skul_data.users.models.school_admin import AdministratorProfile
from skul_data.tests.users_tests.test_helpers_admins import (
    create_test_school,
    create_test_teacher,
)


@override_settings(ACTION_LOG_TEST_MODE=True)
class AdministratorLoggingTest(APITestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.client.force_authenticate(user=self.admin_user)
        self.teacher = create_test_teacher(self.school)
        self.regular_user = User.objects.create_user(
            email="regular@test.com",
            username="regular",
            password="testpass",
            first_name="Regular",
            last_name="User",
            user_type=User.OTHER,
        )

    def test_make_teacher_administrator_logging(self):
        url = reverse("user-make-administrator", args=[self.teacher.user.id])
        response = self.client.post(url)

        # Debug: Print response details if test fails
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertEqual(response.status_code, 200)

        # Check the log was created
        log = ActionLog.objects.filter(
            user=self.admin_user, metadata__action_type="TEACHER_TO_ADMIN"
        ).first()

        # Debug: Print available logs if none found
        if not log:
            all_logs = ActionLog.objects.filter(user=self.admin_user)
            print(
                f"Available logs: {[(l.action, l.metadata.get('action_type', 'NO_TYPE')) for l in all_logs]}"
            )

        self.assertIsNotNone(log)
        self.assertEqual(log.category, ActionCategory.UPDATE.name)
        self.assertTrue(log.metadata["new_status"])
        self.assertEqual(log.metadata["school_id"], self.school.id)

    def test_make_regular_user_administrator_logging(self):
        url = reverse("user-make-administrator", args=[self.regular_user.id])
        response = self.client.post(url, {"position": "Test Admin"})

        # Debug: Print response details if test fails
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertEqual(response.status_code, 200)

        # Check the log was created
        log = ActionLog.objects.filter(
            user=self.admin_user, metadata__action_type="USER_TO_ADMIN"
        ).first()

        # Debug: Print available logs if none found
        if not log:
            all_logs = ActionLog.objects.filter(user=self.admin_user)
            print(
                f"Available logs: {[(l.action, l.metadata.get('action_type', 'NO_TYPE')) for l in all_logs]}"
            )

        self.assertIsNotNone(log)
        self.assertEqual(log.category, ActionCategory.CREATE.name)
        self.assertEqual(log.metadata["position"], "Test Admin")
        self.assertEqual(log.metadata["school_id"], self.school.id)

    def test_remove_teacher_administrator_logging(self):
        # First make the teacher an admin
        self.teacher.is_administrator = True
        self.teacher.save()

        url = reverse("user-remove-administrator", args=[self.teacher.user.id])
        response = self.client.post(url)

        # Debug: Print response details if test fails
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertEqual(response.status_code, 200)

        # Check the log was created
        log = ActionLog.objects.filter(
            user=self.admin_user, metadata__action_type="REMOVE_ADMIN_FROM_TEACHER"
        ).first()

        # Debug: Print available logs if none found
        if not log:
            all_logs = ActionLog.objects.filter(user=self.admin_user)
            print(
                f"Available logs: {[(l.action, l.metadata.get('action_type', 'NO_TYPE')) for l in all_logs]}"
            )

        self.assertIsNotNone(log)
        self.assertEqual(log.category, ActionCategory.UPDATE.name)
        self.assertFalse(log.metadata["new_status"])
        self.assertEqual(log.metadata["school_id"], self.school.id)

    def test_remove_administrator_profile_logging(self):
        # Create an admin profile first
        admin_profile = AdministratorProfile.objects.create(
            user=self.regular_user, school=self.school, position="Test Admin"
        )

        url = reverse("user-remove-administrator", args=[self.regular_user.id])
        response = self.client.post(url)

        # Debug: Print response details if test fails
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertEqual(response.status_code, 200)

        # Check the log was created
        log = ActionLog.objects.filter(
            user=self.admin_user, metadata__action_type="REMOVE_ADMIN_FROM_USER"
        ).first()

        # Debug: Print available logs if none found
        if not log:
            all_logs = ActionLog.objects.filter(user=self.admin_user)
            print(
                f"Available logs: {[(l.action, l.metadata.get('action_type', 'NO_TYPE')) for l in all_logs]}"
            )

        self.assertIsNotNone(log)
        self.assertEqual(log.category, ActionCategory.DELETE.name)
        self.assertEqual(log.metadata["position"], "Test Admin")
        self.assertEqual(log.metadata["school_id"], self.school.id)

    def test_administrator_permission_changes_logging(self):
        # Create an admin profile
        admin_profile = AdministratorProfile.objects.create(
            user=self.regular_user,
            school=self.school,
            position="Test Admin",
            permissions_granted=["view_analytics"],
        )

        # Update permissions
        url = reverse("administrator-detail", args=[admin_profile.id])
        data = {"permissions_granted": ["view_analytics", "manage_users"]}
        response = self.client.patch(url, data, format="json")

        # Debug: Print response details if test fails
        if response.status_code not in [200, 204]:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertIn(response.status_code, [200, 204])

        # Check the log was created
        log = ActionLog.objects.filter(
            user=self.admin_user, metadata__action_type="ADMIN_PERMISSIONS_UPDATE"
        ).first()

        # Debug: Print available logs if none found
        if not log:
            all_logs = ActionLog.objects.filter(user=self.admin_user)
            print(
                f"Available logs: {[(l.action, l.metadata.get('action_type', 'NO_TYPE')) for l in all_logs]}"
            )

        self.assertIsNotNone(log)
        self.assertEqual(log.metadata["added_permissions"], ["manage_users"])
        self.assertEqual(len(log.metadata["current_permissions"]), 2)
        self.assertEqual(log.metadata["school_id"], self.school.id)

    def test_administrator_access_level_change_logging(self):
        # Create an admin profile
        admin_profile = AdministratorProfile.objects.create(
            user=self.regular_user,
            school=self.school,
            position="Test Admin",
            access_level="standard",
        )

        # Update access level
        url = reverse("administrator-detail", args=[admin_profile.id])
        data = {"access_level": "elevated"}
        response = self.client.patch(url, data, format="json")

        # Debug: Print response details if test fails
        if response.status_code not in [200, 204]:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertIn(response.status_code, [200, 204])

        # Check the log was created
        log = ActionLog.objects.filter(
            user=self.admin_user, metadata__action_type="ADMIN_ACCESS_LEVEL_CHANGE"
        ).first()

        # Debug: Print available logs if none found
        if not log:
            all_logs = ActionLog.objects.filter(user=self.admin_user)
            print(
                f"Available logs: {[(l.action, l.metadata.get('action_type', 'NO_TYPE')) for l in all_logs]}"
            )

        self.assertIsNotNone(log)
        self.assertEqual(log.metadata["previous_level"], "standard")
        self.assertEqual(log.metadata["new_level"], "elevated")
        self.assertEqual(log.metadata["school_id"], self.school.id)

    def test_administrator_position_change_logging(self):
        # Create an admin profile
        admin_profile = AdministratorProfile.objects.create(
            user=self.regular_user, school=self.school, position="Junior Admin"
        )

        # Update position
        url = reverse("administrator-detail", args=[admin_profile.id])
        data = {"position": "Senior Admin"}
        response = self.client.patch(url, data, format="json")

        # Debug: Print response details if test fails
        if response.status_code not in [200, 204]:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertIn(response.status_code, [200, 204])

        # Check the log was created
        log = ActionLog.objects.filter(
            user=self.admin_user, metadata__action_type="ADMIN_POSITION_CHANGE"
        ).first()

        # Debug: Print available logs if none found
        if not log:
            all_logs = ActionLog.objects.filter(user=self.admin_user)
            print(
                f"Available logs: {[(l.action, l.metadata.get('action_type', 'NO_TYPE')) for l in all_logs]}"
            )

        self.assertIsNotNone(log)
        self.assertEqual(log.metadata["previous_position"], "Junior Admin")
        self.assertEqual(log.metadata["new_position"], "Senior Admin")
        self.assertEqual(log.metadata["school_id"], self.school.id)


# python manage.py test skul_data.tests.users_tests.test_admins_logging
