from django.test import TestCase
from django.utils import timezone
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.users.models.base_user import User
from skul_data.users.models.school_admin import AdministratorProfile
from skul_data.users.models.teacher import Teacher
from skul_data.tests.users_tests.test_helpers_admins import create_test_school
from skul_data.action_logs.utils.action_log import set_test_mode


class AdministratorSignalLoggingTest(TestCase):
    def setUp(self):
        # Enable test mode for action logging
        set_test_mode(True)

        self.school, self.admin = create_test_school()
        self.user = User.objects.create_user(
            email="admin@test.com",
            username="testadmin",
            password="testpass",
            first_name="Admin",
            last_name="User",
            user_type=User.ADMINISTRATOR,
        )
        # Set current user for signals
        User.set_current_user(self.admin)

    def tearDown(self):
        # Reset test mode
        set_test_mode(False)
        User.set_current_user(None)

    def test_administrator_creation_logging(self):
        """Test signal logs when administrator profile is created"""
        admin_profile = AdministratorProfile.objects.create(
            user=self.user,
            school=self.school,
            position="Principal",
            access_level="elevated",
        )

        log = ActionLog.objects.filter(
            metadata__action_type="ADMIN_PROFILE_CREATE"
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.category, ActionCategory.CREATE.name)
        self.assertEqual(log.metadata["position"], "Principal")
        self.assertEqual(log.metadata["school_id"], self.school.id)

    def test_administrator_update_logging(self):
        """Test signal logs when administrator profile is updated"""
        admin_profile = AdministratorProfile.objects.create(
            user=self.user,
            school=self.school,
            position="Principal",
            access_level="standard",
        )

        # Update the profile
        admin_profile.access_level = "elevated"
        admin_profile.save()

        log = ActionLog.objects.filter(
            metadata__action_type="ADMIN_PROFILE_UPDATE"
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.category, ActionCategory.UPDATE.name)
        self.assertEqual(log.metadata["changed_fields"], ["access_level"])
        self.assertEqual(log.metadata["school_id"], self.school.id)

    def test_administrator_deletion_logging(self):
        """Test signal logs when administrator profile is deleted"""
        admin_profile = AdministratorProfile.objects.create(
            user=self.user, school=self.school, position="Principal"
        )

        admin_profile.delete()

        log = ActionLog.objects.filter(
            metadata__action_type="ADMIN_PROFILE_DELETE"
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.category, ActionCategory.DELETE.name)
        self.assertEqual(log.metadata["position"], "Principal")
        self.assertEqual(log.metadata["school_id"], self.school.id)


class TeacherSignalLoggingTest(TestCase):
    def setUp(self):
        # Enable test mode for action logging
        set_test_mode(True)

        self.school, self.admin = create_test_school()
        self.teacher = Teacher.objects.create(
            user=User.objects.create_user(
                email="teacher@test.com",
                username="teacher",
                password="testpass",
                first_name="Test",
                last_name="Teacher",
                user_type=User.TEACHER,
            ),
            school=self.school,
            phone_number="+254700000000",
            status="ACTIVE",
        )
        # Set current user for signals
        User.set_current_user(self.admin)

    def tearDown(self):
        # Reset test mode
        set_test_mode(False)
        User.set_current_user(None)

    def test_teacher_admin_status_change_logging(self):
        """Test signal logs when teacher is made administrator"""
        self.teacher.is_administrator = True
        self.teacher.administrator_since = timezone.now().date()
        self.teacher.save()

        log = ActionLog.objects.filter(
            metadata__action_type="TEACHER_ADMIN_STATUS_CHANGE"
        ).first()

        self.assertIsNotNone(log)
        self.assertTrue(log.metadata["new_status"])
        self.assertEqual(log.metadata["previous_status"], False)
        self.assertEqual(log.metadata["school_id"], self.school.id)

    # def test_teacher_admin_status_removal_logging(self):
    #     """Test signal logs when administrator status is removed"""
    #     self.teacher.is_administrator = True
    #     self.teacher.save()

    #     # Now remove admin status
    #     self.teacher.is_administrator = False
    #     self.teacher.administrator_until = timezone.now().date()
    #     self.teacher.save()

    #     log = ActionLog.objects.filter(
    #         metadata__action_type="TEACHER_ADMIN_STATUS_CHANGE"
    #     ).last()  # Get the most recent log

    #     self.assertIsNotNone(log)
    #     self.assertFalse(log.metadata["new_status"])
    #     self.assertEqual(log.metadata["previous_status"], True)
    #     self.assertEqual(log.metadata["school_id"], self.school.id)
    #     self.assertIsNotNone(log.metadata["administrator_until"])

    def test_teacher_admin_status_removal_logging(self):
        """Test signal logs when administrator status is removed"""
        # Clear any existing logs first
        ActionLog.objects.all().delete()

        self.teacher.is_administrator = True
        self.teacher.save()  # This creates the first log

        # Count logs after first save
        first_log_count = ActionLog.objects.filter(
            metadata__action_type="TEACHER_ADMIN_STATUS_CHANGE"
        ).count()

        # Now remove admin status
        self.teacher.is_administrator = False
        self.teacher.administrator_until = timezone.now().date()
        self.teacher.save()  # This should create the second log

        # Get all logs for this action type
        logs = ActionLog.objects.filter(
            metadata__action_type="TEACHER_ADMIN_STATUS_CHANGE"
        ).order_by("timestamp")

        # Should have exactly 2 logs now
        self.assertEqual(logs.count(), 2)

        # Get the second (removal) log
        removal_log = logs.last()

        self.assertIsNotNone(removal_log)
        self.assertFalse(removal_log.metadata["new_status"])
        self.assertEqual(removal_log.metadata["previous_status"], True)
        self.assertEqual(removal_log.metadata["school_id"], self.school.id)
        self.assertIsNotNone(removal_log.metadata["administrator_until"])


# python manage.py test skul_data.tests.users_tests.test_admins_signals
