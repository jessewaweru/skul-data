from django.test import TestCase, RequestFactory
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from skul_data.tests.users_tests.users_factories import UserFactory
from skul_data.users.models.session import UserSession
from skul_data.users.middleware.session import SessionTrackingMiddleware


User = get_user_model()


class SessionTrackingMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.middleware = SessionTrackingMiddleware(lambda r: None)

    def test_process_session_authenticated(self):
        request = self.factory.get("/")
        request.user = self.user
        request.session = Session.objects.create(
            session_key="test_session",
            expire_date=timezone.now() + timezone.timedelta(days=1),
        )
        request.META["HTTP_USER_AGENT"] = "Test User Agent"
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        self.middleware(request)
        self.assertEqual(UserSession.objects.count(), 1)
        session = UserSession.objects.first()
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.session.session_key, "test_session")

    def test_process_session_unauthenticated(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()  # Or just don't set it at all
        request.session = Session.objects.create(
            session_key="test_session",
            expire_date=timezone.now() + timezone.timedelta(days=1),
        )

        self.middleware(request)
        self.assertEqual(UserSession.objects.count(), 0)

    def test_get_client_ip(self):
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "192.168.1.1, 10.0.0.1"
        ip = self.middleware.get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

        del request.META["HTTP_X_FORWARDED_FOR"]
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        ip = self.middleware.get_client_ip(request)
        self.assertEqual(ip, "127.0.0.1")


# python manage.py test skul_data.tests.users_tests.test_users_middleware
