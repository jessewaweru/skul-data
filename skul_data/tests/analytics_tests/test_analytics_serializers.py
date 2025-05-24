from django.test import TestCase
from skul_data.analytics.serializers.analytics import (
    AnalyticsDashboardSerializer,
    CachedAnalyticsSerializer,
    AnalyticsAlertSerializer,
    AnalyticsFilterSerializer,
)
from skul_data.tests.analytics_tests.test_helpers import (
    create_test_school,
    create_test_dashboard,
    create_test_cached_analytics,
    create_test_alert,
)


class AnalyticsDashboardSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.dashboard = create_test_dashboard(self.school, self.admin)

    def test_serializer(self):
        serializer = AnalyticsDashboardSerializer(instance=self.dashboard)
        data = serializer.data
        self.assertEqual(data["name"], "Test Dashboard")
        self.assertEqual(data["school"]["name"], self.school.name)
        self.assertEqual(data["created_by"]["email"], self.admin.email)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)


class CachedAnalyticsSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.cached = create_test_cached_analytics(self.school)

    def test_serializer(self):
        serializer = CachedAnalyticsSerializer(instance=self.cached)
        data = serializer.data
        self.assertEqual(data["analytics_type"], "overview")
        self.assertEqual(data["school"]["name"], self.school.name)
        self.assertEqual(data["data"], {"metric1": 10, "metric2": 20})
        self.assertIn("computed_at", data)


class AnalyticsAlertSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.alert = create_test_alert(self.school)

    def test_serializer(self):
        serializer = AnalyticsAlertSerializer(instance=self.alert)
        data = serializer.data
        print(data)
        self.assertEqual(data["alert_type"], "ATTENDANCE")
        self.assertEqual(data["title"], "Test Alert")
        self.assertEqual(data["school"]["name"], self.school.name)
        self.assertFalse(data["is_read"])
        self.assertIn("created_at", data)


class AnalyticsFilterSerializerTest(TestCase):
    def test_valid_serializer(self):
        data = {"date_range": "weekly"}
        serializer = AnalyticsFilterSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_invalid_serializer(self):
        data = {"start_date": "2023-01-01"}  # Missing end_date
        serializer = AnalyticsFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_date_range_validation(self):
        valid_data = [
            {"date_range": "daily"},
            {"date_range": "weekly"},
            {"date_range": "monthly"},
            {"date_range": "termly"},
            {"start_date": "2023-01-01", "end_date": "2023-01-31"},
        ]

        for data in valid_data:
            serializer = AnalyticsFilterSerializer(data=data)
            self.assertTrue(serializer.is_valid(), msg=f"Failed for {data}")


# python manage.py test skul_data.tests.analytics_tests.test_analytics_serializers
