from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from skul_data.analytics.models.analytics import (
    AnalyticsDashboard,
    CachedAnalytics,
    AnalyticsAlert,
)
from skul_data.tests.analytics_tests.test_helpers import create_test_school


class AnalyticsDashboardModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()

    def test_create_dashboard(self):
        dashboard = AnalyticsDashboard.objects.create(
            name="Test Dashboard",
            school=self.school,
            created_by=self.admin,
            config={"widgets": ["attendance"]},
        )
        self.assertEqual(dashboard.school, self.school)
        self.assertEqual(dashboard.created_by, self.admin)
        self.assertFalse(dashboard.is_default)
        self.assertEqual(dashboard.__str__(), f"Test Dashboard ({self.school.name})")

    def test_unique_together_constraint(self):
        AnalyticsDashboard.objects.create(
            name="Test Dashboard",
            school=self.school,
            created_by=self.admin,
            config={"widgets": ["attendance"]},
        )
        with self.assertRaises(Exception):
            AnalyticsDashboard.objects.create(
                name="Test Dashboard",
                school=self.school,
                created_by=self.admin,
                config={"widgets": ["performance"]},
            )


class CachedAnalyticsModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()

    def test_create_cached_analytics(self):
        cached = CachedAnalytics.objects.create(
            school=self.school,
            analytics_type="overview",
            data={"metric": 10},
            valid_until=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(cached.school, self.school)
        self.assertEqual(cached.analytics_type, "overview")
        self.assertEqual(cached.__str__(), f"overview for {self.school.name}")

    def test_indexes(self):
        # Just verify the model can be queried by school and type
        CachedAnalytics.objects.create(
            school=self.school,
            analytics_type="overview",
            data={"metric": 10},
            valid_until=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(
            CachedAnalytics.objects.filter(
                school=self.school, analytics_type="overview"
            ).count(),
            1,
        )


class AnalyticsAlertModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()

    def test_create_alert(self):
        alert = AnalyticsAlert.objects.create(
            school=self.school,
            alert_type="ATTENDANCE",
            title="Test Alert",
            message="This is a test",
            related_model="Student",
            related_id=1,
        )
        self.assertEqual(alert.school, self.school)
        self.assertFalse(alert.is_read)
        self.assertEqual(alert.__str__(), "Attendance Alert: Test Alert")

    def test_alert_ordering(self):
        alert1 = AnalyticsAlert.objects.create(
            school=self.school,
            alert_type="ATTENDANCE",
            title="Alert 1",
            message="First alert",
            created_at=timezone.now() - timedelta(days=1),
        )
        alert2 = AnalyticsAlert.objects.create(
            school=self.school,
            alert_type="PERFORMANCE",
            title="Alert 2",
            message="Second alert",
        )
        alerts = list(AnalyticsAlert.objects.all())
        self.assertEqual(alerts[0], alert2)  # Most recent first
        self.assertEqual(alerts[1], alert1)


# python manage.py test skul_data.tests.analytics_tests.test_analytics_models
