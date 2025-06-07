from rest_framework.test import APITestCase
from skul_data.tests.parents_tests.test_helpers import (
    create_test_school,
    create_test_parent,
)
from skul_data.users.models.base_user import User
from skul_data.users.models.parent import Parent


class ParentBulkImportUtilsTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)

    def test_send_parent_email_success(self):
        # In a real test, you would mock the email sending
        from django.core import mail
        from skul_data.users.utils.parent import send_parent_email

        result = send_parent_email(self.parent, "Test Subject", "Test Message")

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test Subject")
        self.assertEqual(mail.outbox[0].to, [self.parent.email])

    def test_send_parent_email_invalid(self):
        from skul_data.users.utils.parent import send_parent_email

        # Create parent with invalid email
        user = User.objects.create_user(
            email="invalid",
            username="invalid",
            password="testpass",
            user_type=User.PARENT,
        )
        parent = Parent.objects.create(user=user, school=self.school)

        result = send_parent_email(parent, "Test Subject", "Test Message")

        self.assertFalse(result)


# python manage.py test skul_data.tests.parents_tests.test_parents_utils
