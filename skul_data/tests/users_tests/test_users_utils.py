from django.test import TestCase
from django.core import mail
from django.conf import settings

from skul_data.tests.users_tests.users_factories import ParentFactory
from skul_data.users.utils.parent import send_parent_email


class ParentUtilsTest(TestCase):
    def setUp(self):
        self.parent = ParentFactory()
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    def test_send_parent_email_success(self):
        result = send_parent_email(self.parent, "Test Subject", "Test Message")
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test Subject")
        self.assertEqual(mail.outbox[0].to[0], self.parent.email)

    def test_send_parent_email_failure(self):
        # Test with invalid email to trigger failure
        self.parent.user.email = "invalid-email"
        self.parent.user.save()
        result = send_parent_email(self.parent, "Test Subject", "Test Message")
        self.assertFalse(result)


# python manage.py test skul_data.tests.users_tests.test_users_utils
