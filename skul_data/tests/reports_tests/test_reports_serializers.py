from django.test import TestCase
from rest_framework.exceptions import ValidationError
from skul_data.reports.models.report import TermReportRequest
from skul_data.tests.reports_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_parent,
    create_test_student,
    create_test_report_template,
    create_test_generated_report,
    create_test_academic_record,
)
from skul_data.reports.serializers.report import (
    ReportTemplateSerializer,
    GeneratedReportSerializer,
    TermReportRequestSerializer,
)
from skul_data.reports.serializers.academic_record import AcademicRecordSerializer


class ReportTemplateSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.template = create_test_report_template(
            school=self.school, created_by=self.admin
        )
        self.serializer = ReportTemplateSerializer(instance=self.template)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "name",
                "template_type",
                "description",
                "content",
                "is_system",
                "school",
                "created_by",
                "created_at",
                "updated_at",
                "preferred_format",
            },
        )

    def test_school_field(self):
        data = self.serializer.data
        self.assertEqual(data["school"]["id"], self.school.id)
        self.assertEqual(data["school"]["name"], self.school.name)

    def test_created_by_field(self):
        data = self.serializer.data
        self.assertEqual(data["created_by"]["id"], self.admin.id)
        self.assertEqual(data["created_by"]["email"], self.admin.email)


class GeneratedReportSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.template = create_test_report_template(
            school=self.school, created_by=self.admin
        )
        self.report = create_test_generated_report(
            school=self.school, report_type=self.template, generated_by=self.admin
        )
        self.serializer = GeneratedReportSerializer(instance=self.report)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "title",
                "report_type",
                "school",
                "generated_by",
                "generated_at",
                "status",
                "file",
                "file_format",
                "data",
                "parameters",
                "notes",
                "is_public",
                "allowed_roles",
                "allowed_users",
                "related_class",
                "related_students",
                "related_teachers",
                "requires_approval",
                "approved_by",
                "approved_at",
                "valid_until",
            },
        )

    def test_report_type_field(self):
        data = self.serializer.data
        self.assertEqual(data["report_type"]["id"], self.template.id)
        self.assertEqual(data["report_type"]["name"], self.template.name)

    def test_generated_by_field(self):
        data = self.serializer.data
        self.assertEqual(data["generated_by"]["id"], self.admin.id)
        self.assertEqual(data["generated_by"]["email"], self.admin.email)


class AcademicRecordSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.student = create_test_student(self.school)
        self.record = create_test_academic_record(
            student=self.student, subject="Math", teacher=self.teacher
        )
        self.serializer = AcademicRecordSerializer(instance=self.record)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "student",
                "subject",
                "teacher",
                "term",
                "school_year",
                "score",
                "grade",
                "subject_comments",
                "created_at",
                "updated_at",
                "is_published",
                "performance_assessment",
            },
        )

    def test_performance_assessment_field(self):
        data = self.serializer.data
        self.assertEqual(data["performance_assessment"], "Good performance")

    def test_validation(self):
        data = {
            "student": self.student.id,
            "subject": "Math",
            "score": 105,  # Invalid score
            "term": "Term 1",
            "school_year": "2023",
        }
        serializer = AcademicRecordSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class TermReportRequestSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)
        self.request = TermReportRequest.objects.create(
            student=self.student,
            parent=self.parent.user,
            term="Term 1",
            school_year="2023",
            status="PENDING",
        )
        self.serializer = TermReportRequestSerializer(instance=self.request)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "student",
                "parent",
                "term",
                "school_year",
                "status",
                "generated_report",
                "requested_at",
                "completed_at",
            },
        )

    def test_student_field(self):
        data = self.serializer.data
        self.assertEqual(
            data["student"]["id"], self.student.id
        )  # Check ID in nested object

    def test_parent_field(self):
        data = self.serializer.data
        self.assertEqual(
            data["parent"]["id"], self.parent.user.id
        )  # Check ID in nested object


# python manage.py test skul_data.tests.reports_tests.test_reports_serializers
