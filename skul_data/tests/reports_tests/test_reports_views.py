import json
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status
from skul_data.tests.reports_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_parent,
    create_test_student,
    create_test_class,
    create_test_report_template,
    create_test_generated_report,
    create_test_academic_record,
)
from skul_data.reports.models.report import (
    ReportTemplate,
    GeneratedReport,
    TermReportRequest,
)
from skul_data.action_logs.models.action_log import ActionCategory
from unittest.mock import patch


class ReportTemplateViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)
        self.template = create_test_report_template(
            school=self.school, created_by=self.admin
        )
        self.url = reverse("report-template-list")

    def test_list_templates(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], self.template.name)

    def test_create_template(self):
        data = {
            "name": "New Template",
            "template_type": "ATTENDANCE",
            "description": "New template description",
            "content": {"fields": [], "layout": "portrait"},
            "is_system": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ReportTemplate.objects.count(), 2)

    def test_retrieve_template(self):
        url = reverse("report-template-detail", args=[self.template.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], self.template.name)

    def test_update_template(self):
        url = reverse("report-template-detail", args=[self.template.id])
        data = {"name": "Updated Template Name"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template.refresh_from_db()
        self.assertEqual(self.template.name, "Updated Template Name")

    def test_delete_template(self):
        url = reverse("report-template-detail", args=[self.template.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ReportTemplate.objects.count(), 0)


class GeneratedReportViewSetTest(APITestCase):
    def setUp(self):
        # Enable test mode for action logging
        from skul_data.action_logs.utils.action_log import set_test_mode

        set_test_mode(True)
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)
        self.template = create_test_report_template(
            school=self.school, created_by=self.admin
        )
        self.report = create_test_generated_report(
            school=self.school, report_type=self.template, generated_by=self.admin
        )
        self.url = reverse("generated-report-list")

    def tearDown(self):
        # Disable test mode after tests
        from skul_data.action_logs.utils.action_log import set_test_mode

        set_test_mode(False)

    def test_list_reports(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], self.report.title)

    def test_retrieve_report(self):
        url = reverse("generated-report-detail", args=[self.report.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], self.report.title)

    def test_approve_report(self):
        self.report.requires_approval = True
        self.report.save()

        url = reverse("generated-report-approve", args=[self.report.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "PUBLISHED")
        self.assertEqual(self.report.approved_by, self.admin)

    def test_create_report(self):
        file = SimpleUploadedFile(
            "test_report.pdf", b"test content", content_type="application/pdf"
        )

        data = {
            "title": "New Report",
            "report_type": self.template.id,
            "status": "DRAFT",
            "file": file,
            "file_format": "PDF",
            "data": json.dumps({"test": "data"}),  # Convert dict to JSON string
            "parameters": json.dumps({}),  # Convert dict to JSON string
        }

        response = self.client.post(self.url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GeneratedReport.objects.count(), 2)

    @patch("skul_data.reports.views.report.log_action")
    def test_approve_report_logging(self, mock_log_action):
        # Setup
        self.report.requires_approval = True
        self.report.save()

        url = reverse("generated-report-approve", args=[self.report.id])

        # Execute
        response = self.client.post(url)

        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "approved"})

        # Refresh report
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "PUBLISHED")
        self.assertEqual(self.report.approved_by, self.admin)

        # Verify logging was called
        mock_log_action.assert_called_once()

        # Verify logging call details
        args, kwargs = mock_log_action.call_args
        self.assertEqual(kwargs["user"], self.admin)
        self.assertIn(f"Approved report {self.report.title}", kwargs["action"])
        self.assertEqual(kwargs["category"], ActionCategory.UPDATE)
        self.assertEqual(kwargs["obj"], self.report)
        self.assertEqual(
            kwargs["metadata"]["previous_status"], "DRAFT"
        )  # or whatever initial status was
        self.assertEqual(kwargs["metadata"]["new_status"], "PUBLISHED")


class AcademicReportViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.client.force_authenticate(user=self.teacher.user)

        # Create class first
        self.school_class = create_test_class(school=self.school, teacher=self.teacher)

        # Create student and assign to class
        self.student = create_test_student(
            school=self.school, first_name="Test", last_name="Student"
        )

        # IMPORTANT: Assign student to the class
        self.student.student_class = self.school_class
        self.student.save()

        self.record = create_test_academic_record(
            student=self.student, subject="Math", teacher=self.teacher
        )

        # Create a report template for the school
        self.report_template = create_test_report_template(
            school=self.school, created_by=self.teacher.user, template_type="ACADEMIC"
        )

        self.url = reverse("academic-report-generate-term-reports")

    def test_generate_term_reports(self):
        data = {
            "class_id": self.school_class.id,
            "term": "Term 1",
            "school_year": "2023",
        }
        response = self.client.post(self.url, data, format="json")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("task_id", response.data)


class TermReportRequestViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()

        # Create parent with user
        self.parent = create_test_parent(self.school)

        # Use the parent's user for authentication
        self.client.force_authenticate(user=self.parent.user)

        # Create student with proper relationships
        self.student = create_test_student(
            school=self.school,
            parent=self.parent,  # Set parent ForeignKey
        )

        # Create a report template for the school
        self.report_template = create_test_report_template(
            school=self.school, created_by=self.admin, template_type="ACADEMIC"
        )

        # # Explicitly make sure both M2M relationships are established
        # self.student.guardians.add(self.parent)
        # self.parent.children.add(self.student)

        # Refresh from DB to ensure relationships are loaded
        self.student.refresh_from_db()
        self.parent.refresh_from_db()

        # Save both objects to ensure relationships are persisted
        self.student.save()
        self.parent.save()

        # Make sure the parent user has a reference to the parent profile
        # The attribute name depends on how your User model relates to Parent
        # Check if this attribute exists and is correct in your model
        if not hasattr(self.parent.user, "parent_profile"):
            # Add this attribute if necessary (depends on your model structure)
            self.parent.user.parent_profile = self.parent

        self.url = reverse("term-report-request-list")

    def test_create_request(self):
        # Verify relationships exist before making request
        self.assertTrue(self.student.parent == self.parent)
        self.assertTrue(self.parent in self.student.guardians.all())
        self.assertTrue(self.student in self.parent.children.all())

        # Print to see what actual values are during the test
        print(
            f"Student parent ID: {self.student.parent.id if self.student.parent else None}"
        )
        print(f"Parent ID: {self.parent.id}")
        print(f"Guardian IDs: {[g.id for g in self.student.guardians.all()]}")

        # This is the key issue - in the serializer validate method it uses the user object
        # but you're comparing with the Parent object in the tests
        # Let's verify the parent.user relationship
        print(f"Parent user ID: {self.parent.user.id}")
        print(f"Authenticated user ID: {self.client.handler._force_user.id}")
        print(
            f"Does user have parent_profile? {hasattr(self.parent.user, 'parent_profile')}"
        )

        data = {"student": self.student.id, "term": "Term 1", "school_year": "2023"}
        # data = {"student_id": self.student.id, "term": "Term 1", "school_year": "2023"}
        response = self.client.post(self.url, data, format="json")

        # Debug output if needed
        if response.status_code != status.HTTP_201_CREATED:
            print("Validation errors:", response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_requests_as_parent(self):
        TermReportRequest.objects.create(
            student=self.student,
            parent=self.parent.user,
            term="Term 1",
            school_year="2023",
            status="PENDING",
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_requests_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        TermReportRequest.objects.create(
            student=self.student,
            parent=self.parent.user,
            term="Term 1",
            school_year="2023",
            status="PENDING",
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


# python manage.py test skul_data.tests.reports_tests.test_reports_views
