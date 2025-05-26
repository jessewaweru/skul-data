from django.http import HttpResponse
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import AnonymousUser
from skul_data.action_logs.middleware.action_log import ActionLogMiddleware
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_school,
)


class ActionLogMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.school, self.admin_user = create_test_school()

        # Create a simple response function that returns a HttpResponse
        self.simple_response = lambda r: HttpResponse(status=200)

    def test_middleware_with_authenticated_user(self):
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
        request = self.factory.get("/some-path/")
        request.user = AnonymousUser()

        middleware = ActionLogMiddleware(self.simple_response)
        middleware(request)

        self.assertEqual(ActionLog.objects.count(), 0)

    def test_middleware_skips_admin_paths(self):
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


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_middleware
