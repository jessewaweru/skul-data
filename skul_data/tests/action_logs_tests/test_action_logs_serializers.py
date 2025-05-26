from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from skul_data.users.models import User
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.action_logs.serializers.action_log import ActionLogSerializer
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_action_log,
    create_test_school,
)
from skul_data.schools.models.school import School


class ActionLogSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.content_type = ContentType.objects.get_for_model(User)

    def test_serializer_fields(self):
        log = create_test_action_log(
            user=self.admin_user,
            category=ActionCategory.CREATE,
            action="Created user",
            content_type=self.content_type,
            object_id=self.admin_user.id,
            metadata={"test": "data"},
        )

        serializer = ActionLogSerializer(log)
        data = serializer.data

        self.assertEqual(data["user"], self.admin_user.id)
        self.assertEqual(data["user_tag"], str(self.admin_user.user_tag))
        self.assertEqual(data["action"], "Created user")
        self.assertEqual(data["category"], "CREATE")
        self.assertEqual(data["category_display"], "Create")
        self.assertEqual(data["ip_address"], "127.0.0.1")
        self.assertEqual(data["user_agent"], "TestAgent/1.0")
        self.assertEqual(data["content_type"], self.content_type.id)
        self.assertEqual(data["object_id"], self.admin_user.id)
        self.assertEqual(data["affected_model"], "User")
        self.assertEqual(data["affected_object"], str(self.admin_user))
        self.assertEqual(data["metadata"], {"test": "data"})
        self.assertIn("timestamp", data)

    def test_user_details_field(self):
        log = create_test_action_log(user=self.admin_user)
        serializer = ActionLogSerializer(log)
        data = serializer.data

        self.assertIn("user_details", data)
        self.assertEqual(data["user_details"]["id"], self.admin_user.id)
        self.assertEqual(data["user_details"]["email"], self.admin_user.email)
        self.assertEqual(data["user_details"]["first_name"], self.admin_user.first_name)
        self.assertEqual(data["user_details"]["last_name"], self.admin_user.last_name)

    def test_serializer_with_no_user(self):
        log = create_test_action_log(user=None)
        serializer = ActionLogSerializer(log)
        data = serializer.data

        self.assertIsNone(data["user"])
        self.assertIsNone(data["user_details"])
        self.assertEqual(str(data["user_tag"]), "00000000-0000-0000-0000-000000000000")


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_serializers
