from django.http import HttpResponse
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import AnonymousUser
from skul_data.action_logs.middleware.action_log import ActionLogMiddleware
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_school,
)
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.schools.models.schoolclass import SchoolClass
from django.core.files.uploadedfile import SimpleUploadedFile
from skul_data.tests.classes_tests.test_helpers import assert_log_exists


class ActionLogMiddlewareTest(TestCase):
    """Tests for the ActionLogMiddleware that logs user actions."""

    def setUp(self):
        self.factory = RequestFactory()
        self.school, self.admin_user = create_test_school()

        # Clear any existing logs
        ActionLog.objects.all().delete()

        # Create a simple response function
        self.simple_response = lambda r: HttpResponse(status=200)

    def test_middleware_with_authenticated_user(self):
        # Clear logs before test
        ActionLog.objects.all().delete()

        request = self.factory.get("/some-path/")
        request.user = self.admin_user
        request.META = {"HTTP_USER_AGENT": "TestAgent/1.0", "REMOTE_ADDR": "127.0.0.1"}

        middleware = ActionLogMiddleware(self.simple_response)
        middleware(request)

        logs = ActionLog.objects.all()
        self.assertEqual(logs.count(), 1)
        log = logs.first()

        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.category, "VIEW")
        self.assertEqual(log.action, "GET /some-path/")
        self.assertEqual(log.ip_address, "127.0.0.1")
        self.assertEqual(log.user_agent, "TestAgent/1.0")

    def test_middleware_with_anonymous_user(self):
        # Clear logs before test
        ActionLog.objects.all().delete()

        request = self.factory.get("/some-path/")
        request.user = AnonymousUser()

        middleware = ActionLogMiddleware(self.simple_response)
        middleware(request)

        self.assertEqual(ActionLog.objects.count(), 0)

    def test_middleware_skips_admin_paths(self):
        # Clear logs before test
        ActionLog.objects.all().delete()

        request = self.factory.get("/admin/")
        request.user = self.admin_user
        request.META = {"HTTP_USER_AGENT": "TestAgent/1.0", "REMOTE_ADDR": "127.0.0.1"}

        middleware = ActionLogMiddleware(self.simple_response)
        middleware(request)

        self.assertEqual(ActionLog.objects.count(), 0)

    def test_middleware_with_different_http_methods(self):
        methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        expected_categories = ["VIEW", "CREATE", "UPDATE", "UPDATE", "DELETE"]

        for method, expected_category in zip(methods, expected_categories):
            request = getattr(self.factory, method.lower())("/some-path/")
            request.user = self.admin_user
            request.META = {
                "HTTP_USER_AGENT": "TestAgent/1.0",
                "REMOTE_ADDR": "127.0.0.1",
            }

            middleware = ActionLogMiddleware(self.simple_response)
            middleware(request)

            log = ActionLog.objects.latest("timestamp")
            self.assertEqual(log.category, expected_category)
            self.assertEqual(log.action, f"{method} /some-path/")


class EnhancedActionLogMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.school, self.admin_user = create_test_school()
        self.simple_response = lambda r: HttpResponse(status=200)

    def test_document_operation_logging(self):
        # Test document upload endpoint
        request = self.factory.post(
            "/documents/upload/",
            data={"file": "test.pdf", "category": "1"},
            content_type="multipart/form-data",
        )
        request.user = self.admin_user
        request.META = {"HTTP_USER_AGENT": "TestAgent/1.0", "REMOTE_ADDR": "127.0.0.1"}

        middleware = ActionLogMiddleware(self.simple_response)
        middleware(request)

        log = ActionLog.objects.first()
        self.assertEqual(log.category, ActionCategory.CREATE)
        self.assertTrue(log.metadata.get("document_operation"))
        self.assertEqual(log.metadata["method"], "POST")
        self.assertEqual(log.metadata["path"], "/documents/upload/")

    def test_document_access_logging(self):
        # Test document view endpoint
        request = self.factory.get("/documents/123/")
        request.user = self.admin_user
        request.META = {"HTTP_USER_AGENT": "TestAgent/1.0", "REMOTE_ADDR": "127.0.0.1"}

        middleware = ActionLogMiddleware(lambda r: HttpResponse(status=200))
        middleware(request)

        log = ActionLog.objects.first()
        self.assertEqual(log.category, ActionCategory.VIEW)
        self.assertTrue(log.metadata.get("document_access"))
        self.assertEqual(log.metadata["document_id"], 123)

    def test_document_bulk_operations(self):
        # Test bulk document operations
        request = self.factory.post(
            "/documents/bulk/",
            data={"ids": "1,2,3", "action": "delete"},
            content_type="application/json",
        )
        request.user = self.admin_user
        request.META = {"HTTP_USER_AGENT": "TestAgent/1.0", "REMOTE_ADDR": "127.0.0.1"}

        middleware = ActionLogMiddleware(self.simple_response)
        middleware(request)

        log = ActionLog.objects.first()
        self.assertEqual(log.category, ActionCategory.CREATE)  # POST is CREATE
        self.assertTrue(log.metadata.get("document_operation"))
        self.assertIn("query_params", log.metadata)

    def test_share_link_download_logging(self):
        # Test share link download endpoint
        request = self.factory.get("/api/documents/share/download/abc123/")
        request.user = self.admin_user
        request.META = {"HTTP_USER_AGENT": "TestAgent/1.0", "REMOTE_ADDR": "127.0.0.1"}

        middleware = ActionLogMiddleware(lambda r: HttpResponse(status=200))
        middleware(request)

        log = ActionLog.objects.first()
        self.assertEqual(log.category, ActionCategory.VIEW)
        self.assertTrue(log.metadata.get("document_operation"))
        self.assertEqual(log.metadata["path"], "/api/documents/share/download/abc123/")
        self.assertIn("token", log.metadata)


class ActionLogMiddlewareTimeTableTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ActionLogMiddleware(lambda r: None)
        self.school, self.admin = create_test_school()
        self.admin.save()  # Ensure admin user is saved
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

    def test_timetable_upload_logging(self):
        # Create file content with proper boundary
        file_content = SimpleUploadedFile(
            "test.pdf",
            b"%PDF-1.4\n...actual PDF content...",  # Mimic real PDF content
            content_type="application/pdf",
        )

        # Create the request properly with format=multipart
        request = self.factory.post(
            "/api/timetables/",
            {
                "school_class": str(self.school_class.id),
                "description": "Test",
                "file": file_content,
            },
            format="multipart",  # This ensures proper boundary generation
        )
        request.user = self.admin

        # Clear any existing logs
        ActionLog.objects.all().delete()

        # Create a proper mock response
        mock_response = type(
            "MockResponse",
            (),
            {"status_code": 200, "headers": {}, "content": b"Test response"},
        )

        # Initialize middleware with our mock response
        middleware = ActionLogMiddleware(lambda r: mock_response)

        # Process the request
        middleware(request)

        # Verify log was created
        log = ActionLog.objects.filter(
            user=self.admin,
            action="POST /api/timetables/",
            category=ActionCategory.CREATE.value,
        ).first()

        self.assertIsNotNone(log, "Timetable upload log not found")
        self.assertEqual(log.metadata.get("timetable_operation"), True)

        # Check file type (either extension or content type)
        file_type = log.metadata.get("file_type")
        self.assertTrue(
            file_type in ["pdf", "application/pdf"],
            f"Expected file_type to be 'pdf' or 'application/pdf', got {file_type}",
        )

    def test_timetable_download_logging(self):
        request = self.factory.get("/api/timetables/1/download/")
        request.user = self.admin

        # Mock a response with Content-Disposition header
        response = type(
            "Response",
            (),
            {
                "status_code": 200,
                "headers": {
                    "Content-Disposition": 'attachment; filename="timetable.pdf"'
                },
            },
        )

        middleware = ActionLogMiddleware(lambda r: response)

        # Clear any existing logs
        ActionLog.objects.all().delete()

        middleware(request)

        # Verify log was created
        log = ActionLog.objects.filter(
            user=self.admin,
            action="GET /api/timetables/1/download/",
            category=ActionCategory.VIEW.value,
        ).first()

        self.assertIsNotNone(log, "Timetable download log not found")
        self.assertEqual(log.metadata.get("timetable_operation"), True)
        self.assertEqual(log.metadata.get("file_download"), True)
        self.assertEqual(log.metadata.get("downloaded_filename"), "timetable.pdf")


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_middleware
