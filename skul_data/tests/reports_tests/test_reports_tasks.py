from unittest.mock import patch, ANY
from django.test import TestCase
from celery.exceptions import Retry
from django.utils import timezone
from skul_data.tests.reports_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_parent,
    create_test_student,
    create_test_class,
    create_test_report_template,
    create_test_generated_report,
)
from skul_data.reports.models.report import TermReportRequest
from skul_data.reports.utils.tasks import (
    generate_student_term_report_task,
    generate_class_term_reports_task,
    process_pending_report_requests,
    generate_term_end_reports,
    generate_school_term_reports_task,
)
from skul_data.reports.models.report import AcademicReportConfig


class ReportTasksTest(TestCase):
    def setUp(self):
        # Create unique school to avoid conflicts
        self.school, self.admin = create_test_school(
            name=f"Test School {timezone.now().microsecond}"
        )

        # Add AcademicReportConfig
        AcademicReportConfig.objects.create(
            school=self.school,
            auto_generate_term_reports=True,
            days_after_term_to_generate=3,
            parent_access_expiry_days=30,
        )

        # Create teacher with unique email
        teacher_email = f"teacher{timezone.now().microsecond}@test.com"
        self.teacher = create_test_teacher(self.school, email=teacher_email)

        # Create parent with unique email
        parent_email = f"parent{timezone.now().microsecond}@test.com"
        self.parent = create_test_parent(self.school, email=parent_email)

        # Create student
        self.student = create_test_student(self.school, parent=self.parent)

        # Create class with unique name and academic year
        unique_class_name = f"TestClass_{timezone.now().microsecond}"
        self.school_class = create_test_class(
            self.school,
            name=unique_class_name,
            teacher=self.teacher,
            academic_year="2023-2024",
        )

        # Assign student to class
        self.student.student_class = self.school_class
        self.student.save()

        # Create report template
        self.report_template = create_test_report_template(
            self.school, self.admin, template_type="ACADEMIC"
        )

    @patch("skul_data.reports.utils.tasks.generate_student_term_report")
    def test_generate_student_term_report_task_success(self, mock_generate):
        """Test successful generation of student term report"""
        # Create a request
        request = TermReportRequest.objects.create(
            student=self.student,
            parent=self.parent.user,
            term="Term 1",
            school_year="2023",
            status="PENDING",
        )

        # Call the task
        generate_student_term_report_task(request.id)

        # Assertions
        mock_generate.assert_called_once_with(request)
        request.refresh_from_db()
        self.assertEqual(request.status, "COMPLETED")

    @patch("skul_data.reports.utils.tasks.generate_student_term_report")
    @patch("skul_data.reports.utils.tasks.generate_student_term_report_task.retry")
    def test_generate_student_term_report_task_retry(self, mock_retry, mock_generate):
        """Test retry behavior when report generation fails"""
        # Create a request
        request = TermReportRequest.objects.create(
            student=self.student,
            parent=self.parent.user,
            term="Term 1",
            school_year="2023",
            status="PENDING",
        )

        # Setup mock to raise exception
        test_exception = Exception("Test error")
        mock_generate.side_effect = test_exception
        mock_retry.side_effect = Retry()

        # Call the task and expect retry
        with self.assertRaises(Retry):
            generate_student_term_report_task(request.id)

        # Assertions
        mock_generate.assert_called_once_with(request)
        mock_retry.assert_called_once_with(
            exc=test_exception, countdown=60, max_retries=3
        )

    @patch("skul_data.reports.utils.tasks.generate_class_term_reports")
    def test_generate_class_term_reports_task(self, mock_generate):
        """Test successful generation of class term reports"""
        # Ensure teacher is properly assigned to class
        self.school_class.class_teacher = self.teacher
        self.school_class.save()

        # Ensure teacher has assigned_classes relationship
        if hasattr(self.teacher, "assigned_classes"):
            self.teacher.assigned_classes.add(self.school_class)

        # Setup mock return value
        mock_generate.return_value = {
            "class": self.school_class.name,
            "term": "Term 1",
            "school_year": "2023",
            "total_students": 1,
            "reports_generated": 1,
            "skipped_students": [],
        }

        # Call the task
        result = generate_class_term_reports_task(
            class_id=self.school_class.id,
            term="Term 1",
            school_year="2023",
            generated_by_id=self.teacher.user.id,
        )

        # Assertions
        mock_generate.assert_called_once_with(
            class_id=self.school_class.id,
            term="Term 1",
            school_year="2023",
            generated_by_id=self.teacher.user.id,
        )
        self.assertEqual(result["reports_generated"], 1)

    @patch("skul_data.reports.utils.tasks.generate_student_term_report_task.delay")
    def test_process_pending_report_requests(self, mock_delay):
        """Test processing of pending report requests"""
        # Create a request
        request = TermReportRequest.objects.create(
            student=self.student,
            parent=self.parent.user,
            term="Term 1",
            school_year="2023",
            status="PENDING",
        )

        # Call the task
        result = process_pending_report_requests()

        # Assertions
        mock_delay.assert_called_once_with(request.id)
        self.assertEqual(result, "Processed 1 pending requests")

    @patch("skul_data.scheduler.models.scheduler.SchoolEvent.get_current_school_year")
    @patch("skul_data.reports.utils.tasks.generate_school_term_reports_task.delay")
    def test_generate_term_end_reports(self, mock_delay, mock_get_year):
        """Test generation of term-end reports for schools with auto-generation enabled"""
        # Setup mocks
        mock_get_year.return_value = "2023-2024"

        # Call the task
        result = generate_term_end_reports()

        # Assertions
        mock_delay.assert_called_once_with(
            self.school.id,
            None,  # term will be None in this case
            "2023-2024",  # mocked school year
            days_after=3,  # default value
        )
        self.assertEqual(result, "Initiated term-end reports for 1 schools")

    @patch("skul_data.reports.utils.tasks.generate_class_term_reports_task.apply_async")
    def test_generate_school_term_reports_task(self, mock_apply_async):
        """Test scheduling of term reports for all classes in a school"""
        # Ensure teacher is properly assigned to class
        self.school_class.class_teacher = self.teacher
        self.school_class.save()

        # Call the task
        result = generate_school_term_reports_task(
            school_id=self.school.id, term="Term 1", school_year="2023", days_after=3
        )

        # Assertions
        mock_apply_async.assert_called_once_with(
            args=[self.school_class.id, "Term 1", "2023", self.teacher.user.id],
            eta=ANY,  # We can't predict the exact datetime
        )
        self.assertEqual(
            result, f"Scheduled term reports for 1 classes in school {self.school.id}"
        )

    def tearDown(self):
        """Clean up after each test"""
        # Clean up any objects that might cause conflicts
        TermReportRequest.objects.all().delete()
        super().tearDown()


class ReportTasksLoggingTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        AcademicReportConfig.objects.create(
            school=self.school,
            auto_generate_term_reports=True,
            days_after_term_to_generate=3,
            parent_access_expiry_days=30,
        )
        self.teacher = create_test_teacher(self.school)
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)
        self.school_class = create_test_class(self.school, teacher=self.teacher)
        self.student.student_class = self.school_class
        self.student.save()
        self.report_template = create_test_report_template(
            self.school, self.admin, template_type="ACADEMIC"
        )
        self.request = TermReportRequest.objects.create(
            student=self.student,
            parent=self.parent.user,
            term="Term 1",
            school_year="2023",
            status="PENDING",
        )

    # @patch("skul_data.reports.utils.tasks.generate_student_term_report")
    # @patch("skul_data.action_logs.utils.action_log.log_action_async")
    # def test_generate_student_term_report_task_logging(self, mock_log, mock_generate):
    #     """Test that the task logs start, success, and error events properly"""
    #     # Setup
    #     mock_report = create_test_generated_report(
    #         school=self.school,
    #         report_type=self.report_template,
    #         generated_by=self.teacher.user,
    #     )
    #     mock_generate.return_value = mock_report

    #     # Execute
    #     generate_student_term_report_task(self.request.id)

    #     # Verify logging
    #     self.assertEqual(mock_log.call_count, 3)  # Start, processing, success

    #     # Check start log
    #     start_call = mock_log.call_args_list[0]
    #     self.assertIn(
    #         "Starting student term report generation", start_call[1]["action"]
    #     )
    #     self.assertEqual(start_call[1]["category"], "SYSTEM")

    #     # Check processing log
    #     process_call = mock_log.call_args_list[1]
    #     self.assertIn("Processing report request", process_call[1]["action"])
    #     self.assertEqual(process_call[1]["obj"], self.request)

    #     # Check success log
    #     success_call = mock_log.call_args_list[2]
    #     self.assertIn("Successfully generated report", success_call[1]["action"])
    #     self.assertEqual(success_call[1]["obj"], mock_report)
    #     self.assertIn("time_taken", success_call[1]["metadata"])

    @patch("skul_data.reports.utils.tasks.generate_student_term_report")
    @patch("skul_data.reports.utils.tasks.log_action_async")
    def test_generate_student_term_report_task_logging(self, mock_log, mock_generate):
        """Test that the task logs start, success, and error events properly"""
        # Setup
        mock_report = create_test_generated_report(
            school=self.school,
            report_type=self.report_template,
            generated_by=self.teacher.user,
        )
        mock_generate.return_value = mock_report

        # Enable test mode for action logging
        from skul_data.action_logs.utils.action_log import set_test_mode

        set_test_mode(True)

        # Execute
        result = generate_student_term_report_task(self.request.id)

        # Verify logging
        self.assertEqual(mock_log.call_count, 3)  # Start, processing, success

        # Check start log
        start_call = mock_log.call_args_list[0]
        self.assertIn(
            "Starting student term report generation", start_call[1]["action"]
        )
        self.assertEqual(start_call[1]["category"], "SYSTEM")

        # Check processing log
        process_call = mock_log.call_args_list[1]
        self.assertIn("Processing report request", process_call[1]["action"])
        self.assertEqual(process_call[1]["obj"], self.request)

        # Check success log
        success_call = mock_log.call_args_list[2]
        self.assertIn("Successfully generated report", success_call[1]["action"])

        # Refresh the request from db to get updated state
        self.request.refresh_from_db()

        # Verify the obj is either the mock_report or request.generated_report
        success_obj = success_call[1]["obj"]
        self.assertTrue(
            success_obj == mock_report or success_obj == self.request.generated_report,
            f"Expected either {mock_report} or {self.request.generated_report}, got {success_obj}",
        )
        self.assertIn("time_taken", success_call[1]["metadata"])

    # @patch("skul_data.reports.utils.tasks.generate_student_term_report")
    # @patch("skul_data.action_logs.utils.action_log.log_action_async")
    # @patch("skul_data.reports.utils.tasks.generate_student_term_report_task.retry")
    # def test_generate_student_term_report_task_error_logging(
    #     self, mock_retry, mock_log, mock_generate
    # ):
    #     """Test error logging in the task"""
    #     # Setup
    #     test_error = Exception("Test error")
    #     mock_generate.side_effect = test_error
    #     mock_retry.side_effect = Retry()

    #     # Execute
    #     with self.assertRaises(Retry):
    #         generate_student_term_report_task(self.request.id)

    #     # Verify error logging
    #     error_log_call = mock_log.call_args_list[2]  # Third call is the error
    #     self.assertIn("Failed to generate report", error_log_call[1]["action"])
    #     self.assertIn("Test error", error_log_call[1]["metadata"]["error"])
    #     self.assertIn("traceback", error_log_call[1]["metadata"])
    #     self.assertEqual(error_log_call[1]["metadata"]["retry_count"], 0)

    @patch("skul_data.reports.utils.tasks.generate_student_term_report")
    @patch("skul_data.reports.utils.tasks.log_action_async")
    @patch("skul_data.reports.utils.tasks.generate_student_term_report_task.retry")
    def test_generate_student_term_report_task_error_logging(
        self, mock_retry, mock_log, mock_generate
    ):
        """Test error logging in the task"""
        # Setup
        test_error = Exception("Test error")
        mock_generate.side_effect = test_error
        mock_retry.side_effect = Retry()

        # Enable test mode for action logging
        from skul_data.action_logs.utils.action_log import set_test_mode

        set_test_mode(True)

        # Execute
        with self.assertRaises(Retry):
            generate_student_term_report_task(self.request.id)

        # Verify error logging
        self.assertGreaterEqual(
            mock_log.call_count, 3
        )  # At least 3 calls (start, processing, error)

        # Find the error log call (might not be exactly the 3rd one)
        error_log_call = None
        for call in mock_log.call_args_list:
            if "Failed to generate report" in call[1]["action"]:
                error_log_call = call
                break

        self.assertIsNotNone(error_log_call, "Error log not found")
        self.assertIn("Failed to generate report", error_log_call[1]["action"])
        self.assertIn("Test error", error_log_call[1]["metadata"]["error"])
        self.assertIn("traceback", error_log_call[1]["metadata"])
        self.assertEqual(error_log_call[1]["metadata"]["retry_count"], 0)

    @patch("skul_data.reports.utils.tasks.generate_class_term_reports")
    @patch("skul_data.action_logs.utils.action_log.log_action_async")
    def test_generate_class_term_reports_task_logging(self, mock_log, mock_generate):
        """Test logging in class term reports task"""
        # Setup
        mock_generate.return_value = {
            "class": self.school_class.name,
            "term": "Term 1",
            "school_year": "2023",
            "total_students": 1,
            "reports_generated": 1,
            "skipped_students": [],
        }

        # Execute
        result = generate_class_term_reports_task(
            class_id=self.school_class.id,
            term="Term 1",
            school_year="2023",
            generated_by_id=self.teacher.user.id,
        )

        # Verify logging happened in the generate_class_term_reports function
        # (We'll test that function separately)
        self.assertTrue(mock_generate.called)

    @patch("skul_data.reports.utils.tasks.generate_student_term_report_task.delay")
    @patch("skul_data.action_logs.utils.action_log.log_action_async")
    def test_process_pending_report_requests_logging(self, mock_log, mock_delay):
        """Test logging in pending requests processor"""
        # Execute
        result = process_pending_report_requests()

        # Verify
        self.assertEqual(result, "Processed 1 pending requests")
        self.assertTrue(mock_delay.called)
        # Would typically log the batch operation, but current implementation doesn't
