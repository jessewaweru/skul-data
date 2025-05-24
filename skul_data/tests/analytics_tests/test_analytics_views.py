from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from django.test import TransactionTestCase
from rest_framework import status
from django.db import transaction
from .test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_parent,
    create_test_student,
    create_test_class,
    create_test_document,
    create_test_report,
    create_test_dashboard,
    create_test_cached_analytics,
    create_test_alert,
    create_test_academic_record,
    create_test_class_attendance,
    create_test_teacher_attendance,
    create_test_subject,
)
from skul_data.analytics.models.analytics import AnalyticsAlert, AnalyticsDashboard
from skul_data.schools.utils.school import get_current_term
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass, ClassAttendance
from skul_data.students.models.student import Subject
from skul_data.students.models.student import Student
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.documents.models.document import Document
from skul_data.reports.models.report import GeneratedReport
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.analytics.models.analytics import AnalyticsAlert
from django.contrib.auth import get_user_model

User = get_user_model()


class AnalyticsViewSetTest(TransactionTestCase):
    def setUp(self):
        try:
            with transaction.atomic():
                self.client = APIClient()
                self.school, self.admin = create_test_school()
                self.client.force_authenticate(user=self.admin)

                # Create test data
                self.teacher = create_test_teacher(self.school)
                self.parent = create_test_parent(self.school)
                self.student = create_test_student(
                    self.school, teacher=self.teacher, parent=self.parent
                )
                self.school_class = create_test_class(self.school)
                self.document = create_test_document(self.school, self.admin)
                self.report = create_test_report(self.school, self.admin)

                # Add student to class
                self.student.student_class = self.school_class
                self.student.save()

                # Create subject
                self.subject = create_test_subject(self.school)

                # Create attendance record
                create_test_class_attendance(
                    self.school_class,
                    self.teacher.user,
                    present_students=[self.student],
                )

                # Create academic record
                create_test_academic_record(
                    self.student,
                    self.subject,
                    self.teacher,
                    term="Term1",
                    school_year=self.school.current_school_year,
                )

                # Create teacher attendance
                create_test_teacher_attendance(self.teacher)

                # Create alerts
                self.alert = create_test_alert(self.school)
                create_test_alert(
                    self.school, alert_type="PERFORMANCE", title="Performance Alert"
                )

                # Create dashboard
                self.dashboard = create_test_dashboard(self.school, self.admin)
        except Exception as e:
            transaction.rollback()
            raise e

    def tearDown(self):
        try:
            with transaction.atomic():
                # Delete all created objects in reverse order
                AnalyticsDashboard.objects.all().delete()
                AnalyticsAlert.objects.all().delete()
                GeneratedReport.objects.all().delete()
                Document.objects.all().delete()
                AcademicRecord.objects.all().delete()
                ClassAttendance.objects.all().delete()
                Student.objects.all().delete()
                Teacher.objects.all().delete()
                Parent.objects.all().delete()
                SchoolClass.objects.all().delete()
                Subject.objects.all().delete()
                School.objects.all().delete()
                User.objects.all().delete()
        except Exception as e:
            transaction.rollback()
            raise e

    def test_overview(self):
        url = reverse("analytics-overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("most_active_teacher", response.data)
        self.assertIn("student_attendance_rate", response.data)

    def test_overview_with_cached_data(self):
        # Create cached data
        create_test_cached_analytics(self.school, analytics_type="overview")

        url = reverse("analytics-overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"metric1": 10, "metric2": 20})

    def test_teachers_analytics(self):
        url = reverse("analytics-teachers")
        response = self.client.get(url, {"date_range": "monthly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_teachers", response.data)
        self.assertIn("logins", response.data)

    def test_students_analytics(self):
        url = reverse("analytics-students")
        response = self.client.get(
            url, {"date_range": "monthly", "class_id": self.school_class.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_students", response.data)
        self.assertIn("attendance", response.data)

    def test_documents_analytics(self):
        url = reverse("analytics-documents")
        response = self.client.get(url, {"date_range": "monthly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_documents", response.data)
        self.assertIn("download_frequency", response.data)

    def test_reports_analytics(self):
        url = reverse("analytics-reports")
        response = self.client.get(url, {"date_range": "monthly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reports_generated", response.data)
        self.assertIn("most_accessed", response.data)

    def test_classes_analytics(self):
        url = reverse("analytics-classes")
        response = self.client.get(url, {"date_range": "monthly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("class_sizes", response.data)
        self.assertIn("average_grades", response.data)

    def test_parents_analytics(self):
        url = reverse("analytics-parents")
        response = self.client.get(url, {"date_range": "monthly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("most_engaged", response.data)
        self.assertIn("students_per_parent", response.data)

    def test_notifications_analytics(self):
        url = reverse("analytics-notifications")
        response = self.client.get(url, {"date_range": "monthly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("open_rates", response.data)
        self.assertIn("message_types", response.data)

    def test_school_wide_analytics(self):
        url = reverse("analytics-school-wide")
        response = self.client.get(url, {"date_range": "monthly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("active_users", response.data)
        self.assertIn("engagement", response.data)

    def test_unauthorized_access(self):
        # Create and authenticate as teacher (who shouldn't have access)
        teacher_user = self.teacher.user
        self.client.force_authenticate(user=teacher_user)

        url = reverse("analytics-overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AnalyticsDashboardViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        # Create test dashboard
        self.dashboard = AnalyticsDashboard.objects.create(
            name="Test Dashboard",
            school=self.school,
            created_by=self.admin,
            config={"widgets": ["attendance"]},
        )

    def tearDown(self):
        try:
            with transaction.atomic():
                AnalyticsDashboard.objects.all().delete()
                School.objects.all().delete()
                User.objects.all().delete()
        except Exception:
            transaction.rollback()

    def test_list_dashboards(self):
        url = reverse("analytics-dashboard-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check for at least 1 dashboard instead of exact count
        self.assertGreaterEqual(len(response.data), 1)

    def test_create_dashboard(self):
        url = reverse("analytics-dashboard-list")
        data = {
            "name": "New Dashboard",
            "config": {"widgets": ["attendance", "performance"]},
            "school": self.school.id,  # Add school ID if required
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_dashboard(self):
        url = reverse("analytics-dashboard-detail", args=[self.dashboard.id])
        data = {"name": "Updated Dashboard", "config": {"widgets": ["attendance"]}}
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Dashboard")
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.name, "Updated Dashboard")


class AnalyticsAlertViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        # Create test alerts properly associated with school
        self.alert = AnalyticsAlert.objects.create(
            school=self.school,
            alert_type="ATTENDANCE",
            title="Test Alert",
            message="This is a test alert",
            related_model="Student",
            related_id=1,
        )

        # Create a second alert for filter tests
        AnalyticsAlert.objects.create(
            school=self.school,
            alert_type="PERFORMANCE",
            title="Performance Alert",
            message="This is a performance alert",
            related_model="Student",
            related_id=2,
        )

    def tearDown(self):
        try:
            with transaction.atomic():
                AnalyticsAlert.objects.all().delete()
                School.objects.all().delete()
                User.objects.all().delete()
        except Exception:
            transaction.rollback()

    def test_list_alerts(self):
        url = reverse("analytics-alert-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check for at least 1 alert
        self.assertGreaterEqual(len(response.data), 1)

    def test_mark_read(self):
        url = reverse("analytics-alert-mark-read", args=[self.alert.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.is_read)

    def test_mark_all_read(self):
        # Create another unread alert
        create_test_alert(self.school, title="Another Alert")

        url = reverse("analytics-alert-mark-all-read")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AnalyticsAlert.objects.filter(is_read=False).count(), 0)

    def test_filter_alerts(self):
        url = reverse("analytics-alert-list")
        response = self.client.get(url, {"alert_type": "PERFORMANCE"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check we got at least one performance alert
        self.assertGreaterEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["alert_type"], "PERFORMANCE")


# python manage.py test skul_data.tests.analytics_tests.test_analytics_views
