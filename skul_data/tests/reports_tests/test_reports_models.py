from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from skul_data.users.models.base_user import User
from skul_data.users.models.parent import Parent
from skul_data.reports.models.report import (
    ReportTemplate,
    ReportAccessLog,
    GeneratedReportAccess,
)
from skul_data.tests.reports_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_student,
    create_test_report_template,
    create_test_generated_report,
    create_test_academic_record,
    create_test_teacher_comment,
)
from skul_data.students.models.student import Subject


class ReportTemplateModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.template = create_test_report_template(
            school=self.school,
            created_by=self.admin,
            template_type="ACADEMIC",
            name="Test Template",
        )

    def test_template_creation(self):
        self.assertEqual(self.template.name, "Test Template")
        self.assertEqual(self.template.template_type, "ACADEMIC")
        self.assertEqual(self.template.school, self.school)
        self.assertEqual(self.template.created_by, self.admin)

    def test_system_template_cannot_have_school(self):
        template = ReportTemplate(
            name="System Template",
            template_type="ACADEMIC",
            is_system=True,
            school=self.school,
            created_by=self.admin,
            content={},
        )
        with self.assertRaises(ValidationError):
            template.clean()

    def test_unique_together_constraint(self):
        # Create first template with explicit name
        create_test_report_template(
            school=self.school,
            created_by=self.admin,
            name="Duplicate Template",
            template_type="ACADEMIC",
        )

        # Try to create duplicate
        with self.assertRaises(Exception):
            ReportTemplate.objects.create(
                name="Duplicate Template",
                template_type="ACADEMIC",
                school=self.school,
                created_by=self.admin,
                content={},
            )


class GeneratedReportModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.template = create_test_report_template(
            school=self.school, created_by=self.admin
        )
        self.report = create_test_generated_report(
            school=self.school, report_type=self.template, generated_by=self.admin
        )

    def test_report_creation(self):
        self.assertEqual(self.report.title, "Test Report")
        self.assertEqual(self.report.report_type, self.template)
        self.assertEqual(self.report.school, self.school)
        self.assertEqual(self.report.generated_by, self.admin)
        self.assertEqual(self.report.status, "DRAFT")
        self.assertEqual(self.report.file_format, "PDF")

    def test_is_valid_property(self):
        # Test with no expiry date
        self.assertTrue(self.report.is_valid)

        # Test with future expiry date
        self.report.valid_until = timezone.now() + timedelta(days=1)
        self.assertTrue(self.report.is_valid)

        # Test with past expiry date
        self.report.valid_until = timezone.now() - timedelta(days=1)
        self.assertFalse(self.report.is_valid)

    def test_is_approved_property(self):
        # Test when approval not required
        self.assertTrue(self.report.is_approved)

        # Test when approval required but not given
        self.report.requires_approval = True
        self.assertFalse(self.report.is_approved)

        # Test when approval required and given
        self.report.approved_by = self.admin
        self.report.approved_at = timezone.now()
        self.assertTrue(self.report.is_approved)


class ReportAccessLogModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.template = create_test_report_template(
            school=self.school, created_by=self.admin
        )
        self.report = create_test_generated_report(
            school=self.school, report_type=self.template, generated_by=self.admin
        )
        self.log = ReportAccessLog.objects.create(
            report=self.report, accessed_by=self.admin, action="VIEWED"
        )

    def test_log_creation(self):
        self.assertEqual(self.log.report, self.report)
        self.assertEqual(self.log.accessed_by, self.admin)
        self.assertEqual(self.log.action, "VIEWED")
        self.assertIsNotNone(self.log.accessed_at)


class GeneratedReportAccessModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent_user = User.objects.create_user(
            email="parent@test.com",
            username="parent",
            password="testpass",
            user_type="parent",
        )
        self.parent = Parent.objects.create(user=self.parent_user, school=self.school)
        self.template = create_test_report_template(
            school=self.school, created_by=self.admin
        )
        self.report = create_test_generated_report(
            school=self.school, report_type=self.template, generated_by=self.admin
        )
        self.access = GeneratedReportAccess.objects.create(
            report=self.report,
            user=self.parent_user,
            expires_at=timezone.now() + timedelta(days=30),
        )

    def test_access_creation(self):
        self.assertEqual(self.access.report, self.report)
        self.assertEqual(self.access.user, self.parent_user)
        self.assertIsNotNone(self.access.granted_at)
        self.assertFalse(self.access.is_expired)
        self.assertFalse(self.access.is_accessed)

    def test_is_expired_property(self):
        # Not expired
        self.access.expires_at = timezone.now() + timedelta(days=1)
        self.access.save()
        self.assertFalse(self.access.is_expired)

        # Expired
        self.access.expires_at = timezone.now() - timedelta(days=1)
        self.access.save()
        self.assertTrue(self.access.is_expired)

    def test_is_accessed_property(self):
        # Not accessed
        self.assertFalse(self.access.is_accessed)

        # Accessed
        self.access.accessed_at = timezone.now()
        self.access.save()
        self.assertTrue(self.access.is_accessed)


class AcademicRecordModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.student = create_test_student(self.school)
        self.record = create_test_academic_record(
            student=self.student, subject="Math", teacher=self.teacher
        )
        # Get the actual subject created
        self.math_subject = self.record.subject

    def test_record_creation(self):
        self.assertEqual(self.record.student, self.student)
        self.assertEqual(self.record.subject, self.math_subject)  # Compare with object
        self.assertEqual(self.record.teacher, self.teacher)
        self.assertEqual(self.record.score, 75.5)
        self.assertEqual(self.record.grade, "B")

    def test_calculate_grade_method(self):
        # Test grade calculation
        self.record.score = 85
        self.record.save()  # This should trigger calculate_grade()
        self.assertEqual(self.record.grade, "A")  # 85 should be A

        self.record.score = 65
        self.record.save()
        self.assertEqual(self.record.grade, "C")  # 65 should be C

        self.record.score = 35
        self.record.save()
        self.assertEqual(self.record.grade, "E")  # 35 should be E

    def test_performance_assessment_property(self):
        self.assertEqual(self.record.performance_assessment, "Good performance")


class TeacherCommentModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.student = create_test_student(self.school)
        self.comment = create_test_teacher_comment(
            student=self.student, teacher=self.teacher
        )

    def test_comment_creation(self):
        self.assertEqual(self.comment.student, self.student)
        self.assertEqual(self.comment.teacher, self.teacher)
        self.assertEqual(self.comment.comment_type, "GENERAL")
        self.assertEqual(self.comment.content, "Test comment")
        self.assertTrue(self.comment.is_approved)

    def test_approve_method(self):
        self.assertIsNone(self.comment.approved_by)
        self.comment.approve(self.admin)
        self.assertEqual(self.comment.approved_by, self.admin)
        self.assertTrue(self.comment.is_approved)


# python manage.py test skul_data.tests.reports_tests.test_reports_models
