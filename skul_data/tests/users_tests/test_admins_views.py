from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from skul_data.users.models.base_user import User
from skul_data.users.models.school_admin import AdministratorProfile
from skul_data.tests.users_tests.test_helpers_admins import (
    create_test_school,
    create_test_teacher,
    create_test_administrator,
)
import uuid


class AdministratorProfileViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.client.force_authenticate(user=self.admin_user)

        # Clear any existing administrators
        AdministratorProfile.objects.all().delete()

        # Create regular administrator
        self.administrator = create_test_administrator(
            school=self.school, email="admin@test.com", position="Principal"
        )

        # Use the administrator we just created as admin_profile
        self.admin_profile = self.administrator

        # self.teacher = create_test_teacher(self.school)
        self.teacher = create_test_teacher(
            self.school,
            email=f"teacher_{uuid.uuid4().hex[:8]}@test.com",
            username=f"teacher_{uuid.uuid4().hex[:8]}",
        )

        # URLs
        self.list_url = reverse("administrator-list")
        self.detail_url = reverse("administrator-detail", args=[self.admin_profile.id])
        self.deactivate_url = reverse(
            "administrator-deactivate", args=[self.admin_profile.id]
        )
        self.permissions_url = reverse("administrator-permissions_options")

    def test_list_administrators(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # Check the count
        self.assertEqual(len(response.data["results"]), 1)  # Check the results list
        self.assertEqual(response.data["results"][0]["id"], self.admin_profile.id)

    def test_retrieve_administrator(self):
        response = self.client.get(self.detail_url)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.admin_profile.id)
        self.assertEqual(response.data["position"], "Principal")

    def test_create_administrator(self):
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
        }

        response = self.client.post(self.list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AdministratorProfile.objects.count(), 2)

    def test_update_administrator(self):
        data = {
            "position": "Senior Principal",
            "access_level": "elevated",
            "permissions_granted": ["manage_users", "manage_teachers"],
        }

        response = self.client.patch(self.detail_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin_profile.refresh_from_db()
        self.assertEqual(self.admin_profile.position, "Senior Principal")
        self.assertEqual(self.admin_profile.access_level, "elevated")

    def test_deactivate_administrator(self):
        response = self.client.post(self.deactivate_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin_profile.refresh_from_db()
        self.assertFalse(self.admin_profile.is_active)

    def test_permissions_options(self):
        response = self.client.get(self.permissions_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(
            len(response.data), 5
        )  # Should return several permission options

    def test_teacher_cannot_access_administrators(self):
        teacher = create_test_teacher(self.school)
        self.client.force_authenticate(user=teacher.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_school_admin_access(self):
        other_school, other_admin_user = create_test_school(name="Other School")
        self.client.force_authenticate(user=other_admin_user)

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_sees_all_admins(self):
        # Create a second administrator explicitly
        second_admin = create_test_administrator(
            school=self.school, email="second@test.com", position="Deputy Principal"
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see both administrators (the one created in setUp and the new one)
        self.assertEqual(response.data["count"], 2)

    def test_regular_admin_sees_only_self(self):
        self.client.force_authenticate(user=self.administrator.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.administrator.id)

    def test_owner_cannot_access_self(self):
        """Ensure owner can't see themselves in admin list"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.list_url)
        admin_ids = [admin["id"] for admin in response.data["results"]]
        self.assertNotIn(self.admin_user.id, admin_ids)


# python manage.py test skul_data.tests.users_tests.test_admins_views
