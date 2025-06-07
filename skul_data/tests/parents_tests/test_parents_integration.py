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
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
import os

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


class ParentBulkImportIntegrationTest(APITestCase):
    def setUp(self):
        from skul_data.action_logs.utils.action_log import set_test_mode

        set_test_mode(True)

        self.school, self.admin = create_test_school()
        self.student1 = create_test_student(self.school, first_name="Alice")
        self.student2 = create_test_student(self.school, first_name="Bob")

        # Admin user
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            username="admin",
            password="testpass",
            user_type=User.SCHOOL_ADMIN,
        )
        SchoolAdmin.objects.create(
            user=self.admin_user,
            school=self.school,
            is_primary=False,
        )
        self.client.force_authenticate(user=self.admin_user)

        self.url = reverse("parent-bulk-import")

        # Enable logging for this test
        self.original_test_env = os.environ.get("TEST", None)
        if "TEST" in os.environ:
            del os.environ["TEST"]

    def tearDown(self):
        # Restore original test environment
        if self.original_test_env is not None:
            os.environ["TEST"] = self.original_test_env

    def test_full_bulk_import_flow(self):
        # 1. Download template
        template_url = reverse("parent-download-template")
        template_response = self.client.get(template_url)
        self.assertEqual(template_response.status_code, status.HTTP_200_OK)

        # 2. Prepare import file
        csv_content = """email,first_name,last_name,phone_number,children_ids,preferred_language
parent1@test.com,John,Doe,+254712345678,1,en
parent2@test.com,Jane,Smith,+254723456789,2,sw
parent3@test.com,Bob,Johnson,,"1,2",fr"""
        csv_file = SimpleUploadedFile(
            "parents.csv", csv_content.encode(), content_type="text/csv"
        )

        # 3. Perform import
        import_data = {
            "file": csv_file,
            "send_welcome_email": True,
            "default_status": "ACTIVE",
        }
        import_response = self.client.post(self.url, import_data, format="multipart")
        self.assertEqual(import_response.status_code, status.HTTP_207_MULTI_STATUS)
        results = import_response.data

        # 4. Verify results
        self.assertEqual(Parent.objects.count(), 3)

        # Check one parent in detail
        parent1 = Parent.objects.get(user__email="parent1@test.com")
        self.assertEqual(parent1.user.first_name, "John")
        self.assertEqual(parent1.phone_number, "+254712345678")
        self.assertEqual(parent1.children.count(), 1)
        self.assertEqual(parent1.children.first(), self.student1)
        self.assertEqual(parent1.status, "ACTIVE")
        self.assertEqual(parent1.preferred_language, "en")

        # Check parent with multiple children
        parent3 = Parent.objects.get(user__email="parent3@test.com")
        self.assertEqual(parent3.children.count(), 2)

        # 5. Verify notifications were sent (would be mocked in real test)
        from django.core import mail

        self.assertEqual(len(mail.outbox), 3)  # One for each parent

        # 6. Verify audit logs
        from skul_data.action_logs.models.action_log import ActionLog

        logs = ActionLog.objects.filter(
            content_type__model="parent",
            action__icontains="bulk imported",  # Changed to match the logged action
        )
        self.assertEqual(logs.count(), 1)
        self.assertIn(str(len(results["success"])), logs.first().action)


# python manage.py test skul_data.tests.parents_tests.test_parents_integration
