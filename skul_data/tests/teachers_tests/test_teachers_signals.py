from django.test import TestCase
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.tests.teachers_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
)


class TeacherSignalsTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)

    def test_teacher_status_change_signal(self):
        # Test TERMINATED status deactivates user
        self.teacher.status = "TERMINATED"
        self.teacher.termination_date = "2023-12-31"
        self.teacher.save()

        self.teacher.user.refresh_from_db()
        self.assertFalse(self.teacher.user.is_active)

        # Test reactivating when status changes back to ACTIVE
        self.teacher.status = "ACTIVE"
        self.teacher.save()

        self.teacher.user.refresh_from_db()
        self.assertTrue(self.teacher.user.is_active)

    def test_user_post_save_signal(self):
        # Test that teacher profile is NOT created automatically (since school is required)
        user = User.objects.create_user(
            email="newsignal@test.com",
            username="newsignal",
            password="testpass",
            user_type=User.TEACHER,
        )

        # Should not have a profile yet
        self.assertFalse(hasattr(user, "teacher_profile"))

        # Now create the profile with a school
        teacher = Teacher.objects.create(user=user, school=self.school)
        self.assertTrue(hasattr(user, "teacher_profile"))
        self.assertEqual(user.teacher_profile.school, self.school)

    def test_teacher_post_save_signal(self):
        # Test that teacher permissions are assigned on creation
        user = User.objects.create_user(
            email="newperms@test.com",
            username="newperms",
            password="testpass",
            user_type=User.TEACHER,
        )

        teacher = Teacher.objects.create(user=user, school=self.school)

        self.assertIsNotNone(user.role)
        self.assertEqual(user.role.name, "Class Teacher")
        self.assertTrue(user.role.permissions.filter(code="manage_attendance").exists())


# python manage.py test skul_data.tests.teachers_tests.test_teachers_signals
