from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from skul_data.users.models import User
from skul_data.action_logs.models.action_log import ActionCategory, ActionLog
from skul_data.tests.action_logs_tests.test_helpers import (
    create_test_action_log,
    create_test_school,
)
from django.utils import timezone


class ActionLogModelTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()
        self.content_type = ContentType.objects.get_for_model(User)

    def test_action_log_creation(self):
        log = create_test_action_log(
            user=self.admin_user,
            category=ActionCategory.CREATE,
            action="Created user",
            content_type=self.content_type,
            object_id=self.admin_user.id,
        )

        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.user_tag, self.admin_user.user_tag)
        self.assertEqual(log.category, ActionCategory.CREATE)
        self.assertEqual(log.action, "Created user")
        self.assertEqual(log.content_type, self.content_type)
        self.assertEqual(log.object_id, self.admin_user.id)
        self.assertIsNotNone(log.timestamp)

    def test_action_category_choices(self):
        self.assertEqual(ActionCategory.CREATE, "CREATE")
        self.assertEqual(ActionCategory.UPDATE, "UPDATE")
        self.assertEqual(ActionCategory.DELETE, "DELETE")
        self.assertEqual(ActionCategory.VIEW, "VIEW")
        self.assertEqual(ActionCategory.LOGIN, "LOGIN")
        self.assertEqual(ActionCategory.LOGOUT, "LOGOUT")
        self.assertEqual(ActionCategory.UPLOAD, "UPLOAD")
        self.assertEqual(ActionCategory.DOWNLOAD, "DOWNLOAD")
        self.assertEqual(ActionCategory.SHARE, "SHARE")
        self.assertEqual(ActionCategory.SYSTEM, "SYSTEM")
        self.assertEqual(ActionCategory.OTHER, "OTHER")

    def test_affected_model_property(self):
        log = create_test_action_log(
            user=self.admin_user,
            content_type=self.content_type,
            object_id=self.admin_user.id,
        )
        self.assertEqual(log.affected_model, "User")

    def test_affected_model_property_no_content_type(self):
        log = create_test_action_log(user=self.admin_user)
        self.assertIsNone(log.affected_model)

    def test_affected_object_property(self):
        log = create_test_action_log(
            user=self.admin_user,
            content_type=self.content_type,
            object_id=self.admin_user.id,
        )
        self.assertEqual(log.affected_object, str(self.admin_user))

    def test_affected_object_property_no_content_object(self):
        log = create_test_action_log(user=self.admin_user)
        self.assertIsNone(log.affected_object)

    def test_str_representation(self):
        log = create_test_action_log(
            user=self.admin_user,
            category=ActionCategory.CREATE,  # Explicitly providing category
            action="Test action",
        )
        expected_str = f"{self.admin_user.user_tag} - Create - Test action"
        self.assertEqual(str(log), expected_str)

    def test_meta_ordering(self):
        log1 = create_test_action_log(
            user=self.admin_user, timestamp=timezone.now() - timezone.timedelta(days=1)
        )
        log2 = create_test_action_log(user=self.admin_user)

        logs = ActionLog.objects.all()
        self.assertEqual(logs[0], log2)
        self.assertEqual(logs[1], log1)


# python manage.py test skul_data.tests.action_logs_tests.test_action_logs_models
