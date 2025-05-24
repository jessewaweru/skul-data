from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from skul_data.analytics.utils.analytics_generator import (
    get_date_filter,
    get_class_filter,
    get_most_active_teacher,
    get_student_attendance_rate,
    get_most_downloaded_document,
    get_top_performing_class,
    get_reports_generated_count,
    get_teacher_logins,
    get_document_access,
    get_active_users,
    get_engagement_rates,
    get_most_engaged_parents,
)
from skul_data.tests.analytics_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_student,
    create_test_class,
    create_test_document,
    create_test_report,
    create_test_subject,
    create_test_academic_record,
    create_test_class_attendance,
    create_test_action_log,
    create_test_parent,
)
from skul_data.action_logs.models.action_log import ActionCategory
from django.contrib.contenttypes.models import ContentType
from skul_data.documents.models.document import Document
from skul_data.reports.models.report import GeneratedReport
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.schools.models.schoolclass import ClassAttendance


class AnalyticsUtilsTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.student = create_test_student(self.school, teacher=self.teacher)
        self.school_class = create_test_class(self.school)
        self.document = create_test_document(self.school, self.admin)
        self.report = create_test_report(
            self.school, self.admin, generated_at=timezone.now()
        )
        self.subject = create_test_subject(self.school)

        # Add student to class
        self.school_class.students.add(self.student)

        # Create action logs for testing
        self.doc_content_type = ContentType.objects.get_for_model(Document)
        self.report_content_type = ContentType.objects.get_for_model(GeneratedReport)

    def test_get_date_filter(self):
        # Test with date_range (commented in original, but should be tested)
        weekly_result = get_date_filter({"date_range": "weekly"})
        self.assertAlmostEqual(
            weekly_result["start"],
            timezone.now() - timedelta(days=7),
            delta=timedelta(seconds=1),
        )
        self.assertAlmostEqual(
            weekly_result["end"], timezone.now(), delta=timedelta(seconds=1)
        )

        # Test with explicit dates
        date_result = get_date_filter(
            {"start_date": "2023-01-01", "end_date": "2023-01-31"}
        )
        self.assertEqual(date_result["start"].strftime("%Y-%m-%d"), "2023-01-01")
        self.assertEqual(date_result["end"].strftime("%Y-%m-%d"), "2023-01-31")

        # Test default case
        default_result = get_date_filter({})
        self.assertAlmostEqual(
            default_result["start"],
            timezone.now() - timedelta(days=30),
            delta=timedelta(seconds=1),
        )
        self.assertAlmostEqual(
            default_result["end"], timezone.now(), delta=timedelta(seconds=1)
        )

    def test_get_class_filter(self):
        # Test with class_id
        filters = {"class_id": self.school_class.id}
        result = get_class_filter(filters)
        self.assertEqual(result, {"student__student_class__id": self.school_class.id})

        # Test without class_id
        result = get_class_filter({})
        self.assertEqual(result, {})

    def test_get_most_active_teacher(self):
        # Create login actions for the teacher
        latest_login = timezone.now() - timedelta(days=1)
        create_test_action_log(
            user=self.teacher.user,
            category=ActionCategory.LOGIN,
            timestamp=timezone.now() - timedelta(days=1),
        )
        create_test_action_log(
            user=self.teacher.user,
            category=ActionCategory.LOGIN,
            timestamp=timezone.now() - timedelta(days=2),
        )
        self.teacher.user.last_login = latest_login
        self.teacher.user.save()

        result = get_most_active_teacher(self.school)
        self.assertIsNotNone(result)
        self.assertEqual(result["user__first_name"], "Test")
        self.assertEqual(result["user__last_name"], "Teacher")
        self.assertEqual(result["login_count"], 2)

    def test_get_reports_generated_count(self):
        # Create reports in current term
        create_test_report(self.school, self.admin)
        create_test_report(self.school, self.admin)

        count = get_reports_generated_count(self.school)
        self.assertEqual(count, 3)  # 2 new + 1 from setUp

    def test_get_student_attendance_rate(self):
        # Clear existing data
        ClassAttendance.objects.all().delete()

        # First attendance: 1/1 = 100%
        create_test_class_attendance(
            self.school_class,
            taken_by=self.admin,
            present_students=[self.student],
            date=timezone.now().date() - timedelta(days=2),
        )
        rate = get_student_attendance_rate(self.school)
        self.assertEqual(rate, 100.0)

        # Add second student
        student2 = create_test_student(
            self.school,
            teacher=self.teacher,
            first_name="Student2",
            email="student2@test.com",
        )
        self.school_class.students.add(student2)

        # Second attendance: 1/2 = 50%
        create_test_class_attendance(
            self.school_class,
            taken_by=self.admin,
            present_students=[self.student],
            date=timezone.now().date() - timedelta(days=1),
        )

        rate = get_student_attendance_rate(self.school)
        self.assertEqual(rate, 75.0)  # (100 + 50)/2 = 75

    def test_get_most_downloaded_document(self):
        # Create download actions
        create_test_action_log(
            user=self.admin,
            category=ActionCategory.DOWNLOAD,
            content_type=self.doc_content_type,
            object_id=self.document.id,
        )
        create_test_action_log(
            user=self.admin,
            category=ActionCategory.DOWNLOAD,
            content_type=self.doc_content_type,
            object_id=self.document.id,
        )

        result = get_most_downloaded_document(self.school)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Test Document")
        self.assertEqual(result["download_count"], 2)

    def test_get_top_performing_class(self):
        # Create academic records
        create_test_academic_record(
            self.student, self.subject, self.teacher, score=85  # A grade
        )

        result = get_top_performing_class(self.school)
        self.assertIsNotNone(result)
        self.assertEqual(result["student__classes__name"], self.school_class.name)
        self.assertEqual(float(result["average_score"]), 85.0)

        # Add another class with lower performance
        class2 = create_test_class(self.school, name="Class 2")
        student2 = create_test_student(
            self.school, teacher=self.teacher, first_name="Student2"
        )
        class2.students.add(student2)

        create_test_academic_record(
            student2, self.subject, self.teacher, score=75  # B grade
        )

        result = get_top_performing_class(self.school)
        self.assertEqual(result["student__classes__name"], self.school_class.name)

    def test_get_teacher_logins(self):
        # Create login actions
        create_test_action_log(
            user=self.teacher.user,
            category=ActionCategory.LOGIN,
            timestamp=timezone.now() - timedelta(days=1),
        )
        create_test_action_log(
            user=self.teacher.user,
            category=ActionCategory.LOGIN,
            timestamp=timezone.now() - timedelta(days=2),
        )
        self.teacher.user.last_login = timezone.now() - timedelta(days=1)
        self.teacher.user.save()

        result = get_teacher_logins(self.school, {"date_range": "monthly"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["login_count"], 2)
        self.assertEqual(result[0]["user__first_name"], "Test")

    def test_get_document_access(self):
        # Create view and download actions
        create_test_action_log(
            user=self.admin,
            category=ActionCategory.VIEW,
            content_type=self.doc_content_type,
            object_id=self.document.id,
        )
        create_test_action_log(
            user=self.admin,
            category=ActionCategory.DOWNLOAD,
            content_type=self.doc_content_type,
            object_id=self.document.id,
        )

        result = get_document_access(self.school, {"date_range": "monthly"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Test Document")
        self.assertEqual(result[0]["view_count"], 1)
        self.assertEqual(result[0]["download_count"], 1)

    def test_get_active_users(self):
        # Create school admin
        admin_profile = SchoolAdmin.objects.create(
            user=self.admin, school=self.school, is_primary=True
        )

        # Create parent
        parent = create_test_parent(
            self.school,
            email="parent_active@test.com",
        )

        # Update last login times
        self.teacher.user.last_login = timezone.now()
        self.teacher.user.save()

        parent.user.last_login = timezone.now()
        parent.user.save()

        self.admin.last_login = timezone.now()
        self.admin.save()

        result = get_active_users(self.school, {"date_range": "daily"})
        self.assertEqual(result["teachers"], 1)
        self.assertEqual(result["parents"], 1)
        self.assertEqual(result["admins"], 1)

    def test_get_engagement_rates(self):
        # Create document and report actions
        create_test_action_log(
            user=self.admin,
            category=ActionCategory.VIEW,
            content_type=self.doc_content_type,
            object_id=self.document.id,
        )
        create_test_action_log(
            user=self.admin,
            category=ActionCategory.VIEW,
            content_type=self.report_content_type,
            object_id=self.report.id,
        )

        result = get_engagement_rates(self.school, {"date_range": "monthly"})
        self.assertEqual(result["documents"], 1)
        self.assertEqual(result["reports"], 1)

    def test_get_most_engaged_parents(self):
        parent = create_test_parent(self.school, email="parent_engaged@test.com")
        parent.user.last_login = timezone.now()
        parent.user.save()

        # Create login action
        create_test_action_log(
            user=parent.user, category=ActionCategory.LOGIN, timestamp=timezone.now()
        )

        result = get_most_engaged_parents(self.school, {"date_range": "monthly"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["user__first_name"], "Test")
        self.assertEqual(result[0]["login_count"], 1)


# python manage.py test skul_data.tests.analytics_tests.test_analytics_utils
