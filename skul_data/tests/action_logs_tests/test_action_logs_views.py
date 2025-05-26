from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_action_log,
    create_test_school,
    create_test_teacher,
)
from django.utils import timezone


class ActionLogViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin_user = create_test_school()
        self.client.force_authenticate(user=self.admin_user)

        # Store base time to ensure consistent relative timestamps
        self.base_time = timezone.now()

        # Create test logs
        self.log1 = create_test_action_log(
            user=self.admin_user,
            category=ActionCategory.CREATE,
            action="Created school",
            timestamp=timezone.now() - timezone.timedelta(days=2),
        )

        self.log2 = create_test_action_log(
            user=self.admin_user,
            category=ActionCategory.UPDATE,
            action="Updated school settings",
            timestamp=timezone.now() - timezone.timedelta(days=1),
        )

        self.log3 = create_test_action_log(
            user=self.admin_user,
            category=ActionCategory.VIEW,
            action="Viewed dashboard",
            timestamp=timezone.now(),
        )

        # Force refresh from database to ensure timestamps are properly set
        self.log1.refresh_from_db()
        self.log2.refresh_from_db()
        self.log3.refresh_from_db()

    def test_list_action_logs(self):
        url = reverse("actionlog-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)  # Directly check response.data length
        self.assertEqual(response.data[0]["id"], self.log3.id)
        self.assertEqual(response.data[1]["id"], self.log2.id)
        self.assertEqual(response.data[2]["id"], self.log1.id)

    def test_filter_by_category(self):
        url = reverse("actionlog-list")
        response = self.client.get(url, {"category": "CREATE"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)  # Directly check response.data length
        self.assertEqual(response.data[0]["id"], self.log1.id)

    def test_filter_by_date_range(self):
        url = reverse("actionlog-list")

        # Use the same base time for consistent filtering
        start_date = (self.base_time - timezone.timedelta(days=1.5)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        end_date = (self.base_time - timezone.timedelta(days=0.5)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )

        response = self.client.get(
            url, {"timestamp__gte": start_date, "timestamp__lte": end_date}
        )

        # DEBUG PRINT STATEMENTS
        print("\nDEBUGGING DATE RANGE FILTER:")
        print(f"Base time: {self.base_time}")
        print(f"Start date: {start_date}")
        print(f"End date: {end_date}")
        print(f"Log1 timestamp: {self.log1.timestamp}")
        print(f"Log2 timestamp: {self.log2.timestamp}")
        print(f"Log3 timestamp: {self.log3.timestamp}")
        print(f"Expected log2 timestamp: {self.base_time - timezone.timedelta(days=1)}")
        print(
            f"Response data IDs: {[log['id'] for log in response.data] if response.data else 'Empty'}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.log2.id)

    def test_search_action_logs(self):
        url = reverse("actionlog-list")
        response = self.client.get(url, {"search": "dashboard"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)  # Directly check response.data length
        self.assertEqual(response.data[0]["id"], self.log3.id)

    def test_model_options_action(self):
        url = reverse("actionlog-model-options")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_category_options_action(self):
        url = reverse("actionlog-category-options")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), len(ActionCategory.choices))

    def test_permissions(self):
        # Test non-admin user can't access
        teacher = create_test_teacher(self.school)
        self.client.force_authenticate(user=teacher.user)

        url = reverse("actionlog-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_views
