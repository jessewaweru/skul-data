from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from skul_data.users.models.parent import Parent
from skul_data.tests.parents_tests.test_helpers import (
    create_test_school,
    create_test_parent,
    create_test_student,
)
from skul_data.users.models.school_admin import SchoolAdmin

User = get_user_model()


class ParentIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)

        # Create a school admin user
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            username="admin",
            password="testpass",
            user_type=User.SCHOOL_ADMIN,
        )

        # Then create the profile that associates with a school:
        SchoolAdmin.objects.create(user=self.admin_user, school=self.school)

        # Create a parent user
        self.parent_user = User.objects.create_user(
            email="parentuser@test.com",
            username="parentuser",
            password="testpass",
            user_type=User.PARENT,
        )
        self.test_parent = Parent.objects.create(
            user=self.parent_user, school=self.school, phone_number="+254766666666"
        )

        # Authenticate as admin by default
        self.client.force_authenticate(user=self.admin_user)

    def test_full_parent_workflow(self):
        # 1. Create a new parent
        create_url = reverse("parent-list")
        create_data = {
            "email": "newparent@test.com",
            "first_name": "New",
            "last_name": "Parent",
            "phone_number": "+254744444444",
            "school": self.school.id,
            "address": "123 New Street",
            "occupation": "New Occupation",
            "password": "testpass123",  # Add this
            "confirm_password": "testpass123",
        }
        response = self.client.post(create_url, create_data, format="json")
        print(response.data)
        self.assertEqual(response.status_code, 201)
        parent_id = response.data["id"]

        # 2. Assign children to the parent
        assign_url = reverse("parent-assign-children", args=[parent_id])
        assign_data = {"student_ids": [self.student.id], "action": "ADD"}
        response = self.client.post(assign_url, assign_data, format="json")
        print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["children_details"]), 1)

        # 3. Change parent status
        status_url = reverse("parent-change-status", args=[parent_id])
        status_data = {"status": "ACTIVE", "reason": "Approved by admin"}
        response = self.client.post(status_url, status_data, format="json")
        print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ACTIVE")

        # 4. Verify status change was logged
        status_changes_url = reverse("parent-status-change-list")
        response = self.client.get(status_changes_url)
        print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(change["parent"] == parent_id for change in response.data))

        # 5. Parent views their own profile
        self.client.force_authenticate(user=self.parent_user)
        detail_url = reverse("parent-detail", args=[self.test_parent.id])
        response = self.client.get(detail_url)
        print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "parentuser@test.com")

        # 6. Parent tries to view another parent's profile (should fail)
        other_detail_url = reverse("parent-detail", args=[parent_id])
        response = self.client.get(other_detail_url)
        print(response.data)
        self.assertEqual(response.status_code, 404)


# python manage.py test skul_data.tests.parents_tests.test_parents_integration
