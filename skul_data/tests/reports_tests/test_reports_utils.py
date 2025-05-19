import json
from unittest.mock import MagicMock, patch
from io import BytesIO
from django.test import TestCase
from skul_data.tests.reports_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_parent,
    create_test_student,
    create_test_class,
    create_test_report_template,
    create_test_generated_report,
    create_test_academic_record,
    create_test_teacher_comment,
)
from skul_data.reports.models.report import (
    GeneratedReport,
    TermReportRequest,
    AcademicReportConfig,
)
from skul_data.reports.utils.report_generator import (
    ReportGenerator,
    generate_report_for_student,
    generate_student_term_report,
    generate_class_term_reports,
    calculate_class_average,
)


class ReportGeneratorTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.student = create_test_student(self.school)
        self.template = create_test_report_template(
            school=self.school, created_by=self.admin, template_type="ACADEMIC"
        )
        self.report_data = {
            "student": {
                "full_name": self.student.full_name,
                "admission_number": "12345",
                "class_name": "Class 1",
            },
            "records": [
                {
                    "subject": "Math",
                    "score": 85.5,
                    "grade": "A",
                    "comments": "Excellent work",
                    "teacher": "Mr. Smith",
                }
            ],
            "teacher_comments": [
                {"type": "GENERAL", "content": "Great student", "teacher": "Mr. Smith"}
            ],
            "class_average": 75.5,
        }

    @patch("skul_data.reports.utils.report_generator.render_to_string")
    @patch("skul_data.reports.utils.report_generator.HTML")
    def test_generate_pdf_report(self, mock_html, mock_render):
        # Setup mocks
        mock_render.return_value = "<html>Test</html>"
        mock_html_instance = MagicMock()
        mock_html.return_value = mock_html_instance
        mock_html_instance.write_pdf.return_value = b"PDF content"

        # Call the method
        report = ReportGenerator.generate_pdf_report(
            template=self.template,
            data=self.report_data,
            title="Test Report",
            user=self.admin,
            school=self.school,
        )

        # Assertions
        self.assertIsInstance(report, GeneratedReport)
        self.assertEqual(report.title, "Test Report")
        self.assertEqual(report.report_type, self.template)
        self.assertEqual(report.file_format, "PDF")
        mock_render.assert_called_once()
        mock_html.assert_called_once()

    @patch("skul_data.reports.utils.report_generator.pd.DataFrame")
    @patch("skul_data.reports.utils.report_generator.BytesIO")
    @patch("skul_data.reports.utils.report_generator.pd.ExcelWriter")
    def test_generate_excel_report(self, mock_excel_writer, mock_bytes_io, mock_df):
        # Setup mocks
        mock_df_instance = MagicMock()
        mock_df.return_value = mock_df_instance

        # Return actual bytes for file content
        mock_bytes_io_instance = BytesIO(b"test excel content")
        mock_bytes_io.return_value = mock_bytes_io_instance

        mock_writer = MagicMock()
        mock_excel_writer.return_value.__enter__.return_value = mock_writer

        # Call the method
        report = ReportGenerator.generate_excel_report(
            template=self.template,
            data=self.report_data,
            title="Test Report",
            user=self.admin,
            school=self.school,
        )

        # Assertions
        self.assertIsInstance(report, GeneratedReport)


class GenerateReportFunctionsTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        # Add this line:
        AcademicReportConfig.objects.create(
            school=self.school, parent_access_expiry_days=30
        )
        self.teacher = create_test_teacher(self.school)
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)
        self.template = create_test_report_template(
            school=self.school,
            created_by=self.admin,
            template_type="ACADEMIC",
            preferred_format="PDF",
        )

        # Create academic records
        self.record = create_test_academic_record(
            student=self.student,
            subject="Math",
            teacher=self.teacher,
            term="Term 1",
            school_year="2023",
            score=85.5,
            grade="A",
            is_published=True,
        )

        # Create teacher comments
        self.comment = create_test_teacher_comment(
            student=self.student,
            teacher=self.teacher,
            term="Term 1",
            school_year="2023",
            is_approved=True,
        )

    @patch.object(ReportGenerator, "generate_pdf_report")
    def test_generate_report_for_student(self, mock_generate):
        # Create template with preferred_format first
        template = create_test_report_template(
            school=self.school,
            created_by=self.admin,
            template_type="ACADEMIC",
            preferred_format="PDF",
        )

        # Debug statements
        print("\n=== DEBUG INFO ===")
        print(f"Student class: {getattr(self.student, 'student_class', None)}")
        print(f"Record is published: {self.record.is_published}")
        print(f"Template exists: {template is not None}")
        print(f"Template type: {template.template_type}")
        print(f"Template format: {template.preferred_format}")
        print("==================\n")

        # Setup mock
        mock_report = create_test_generated_report(
            school=self.school,
            report_type=template,
            generated_by=self.teacher.user,
        )
        mock_generate.return_value = mock_report

        # Ensure student has a class
        test_class = create_test_class(self.school, teacher=self.teacher)
        self.student.student_class = test_class
        self.student.save()

        # Ensure we have published records
        self.record.refresh_from_db()
        self.assertTrue(self.record.is_published)

        # Call the function
        report = generate_report_for_student(
            student=self.student,
            term="Term 1",
            school_year="2023",
            template=template,
            teacher_user=self.teacher.user,
            school=self.school,
            class_average=75.5,
        )

        # Verify
        mock_generate.assert_called_once()
        self.assertEqual(report, mock_report)

    @patch("skul_data.reports.utils.report_generator.generate_report_for_student")
    @patch("skul_data.reports.utils.report_generator.send_report_notification")
    def test_generate_student_term_report(self, mock_send_notification, mock_generate):
        # Create a request
        request = TermReportRequest.objects.create(
            student=self.student,
            parent=self.parent.user,
            term="Term 1",
            school_year="2023",
            status="PENDING",
        )

        # Setup mock
        mock_report = create_test_generated_report(
            school=self.school,
            report_type=self.template,
            generated_by=self.teacher.user,
        )
        mock_generate.return_value = mock_report

        # Call the function
        generate_student_term_report(request)

        # Refresh from db
        request.refresh_from_db()

        # Assertions
        self.assertEqual(request.status, "COMPLETED")
        self.assertEqual(request.generated_report, mock_report)
        self.assertIsNotNone(request.completed_at)
        mock_send_notification.assert_called_once_with(self.parent.user, mock_report)

    @patch("skul_data.reports.utils.report_generator.generate_report_for_student")
    @patch("skul_data.reports.utils.report_generator.send_report_notification")
    def test_generate_class_term_reports(self, mock_send_notification, mock_generate):
        # Create a class with academic year
        school_class = create_test_class(
            self.school, teacher=self.teacher, academic_year="2023"
        )

        # Add student to class through both relationships
        self.student.student_class = school_class
        school_class.students.add(self.student)
        self.student.save()

        # Refresh to ensure relationships are saved
        self.student.refresh_from_db()
        school_class.refresh_from_db()

        # Verify the assignments
        self.assertEqual(self.student.student_class, school_class)
        self.assertIn(self.student, school_class.students.all())

        print(f"Student class: {self.student.student_class}")  # Should show the class
        print(
            f"Class students: {list(school_class.students.all())}"
        )  # Should include the student
        print(
            f"Student in class students: {self.student in school_class.students.all()}"
        )  # Should be True

        # Rest of the test remains the same...
        mock_report = create_test_generated_report(
            school=self.school,
            report_type=self.template,
            generated_by=self.teacher.user,
        )
        mock_generate.return_value = mock_report

        # Call the function
        result = generate_class_term_reports(
            class_id=school_class.id,
            term="Term 1",
            school_year="2023",
            generated_by_id=self.teacher.user.id,
        )

        # Assertions
        self.assertEqual(result["class"], school_class.name)
        self.assertEqual(result["term"], "Term 1")
        self.assertEqual(result["reports_generated"], 1)  # This should now pass
        self.assertEqual(len(result["skipped_students"]), 0)

    def test_calculate_class_average(self):
        # Create another student and record to test average
        student2 = create_test_student(self.school)
        create_test_academic_record(
            student=student2,
            subject="Math",
            teacher=self.teacher,
            term="Term 1",
            school_year="2023",
            score=65.5,
            is_published=True,
        )

        # Calculate average
        average = calculate_class_average(
            school_class=self.student.student_class, term="Term 1", school_year="2023"
        )

        # Assertions (85.5 + 65.5) / 2 = 75.5
        self.assertEqual(average, 75.5)


# python manage.py test skul_data.tests.reports_tests.test_reports_utils
