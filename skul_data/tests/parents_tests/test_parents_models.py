from django.test import TestCase
from django.contrib.auth import get_user_model
from skul_data.users.models.parent import Parent, ParentStatusChange, ParentNotification
from skul_data.tests.parents_tests.test_helpers import (
    create_test_school,
    create_test_parent,
    create_test_student,
)

User = get_user_model()


class ParentModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent_user = User.objects.create_user(
            email="parent@test.com",
            username="parent",
            password="testpass",
            user_type=User.PARENT,
            first_name="Test",
            last_name="Parent",
        )
        self.parent = Parent.objects.create(
            user=self.parent_user,
            school=self.school,
            phone_number="+254700000000",
            status="PENDING",
        )
        self.student = create_test_student(self.school, parent=self.parent)
        # Explicitly add the student to the parent's children
        self.parent.children.add(self.student)

    def test_parent_creation(self):
        self.assertEqual(self.parent.user.email, "parent@test.com")
        self.assertEqual(self.parent.school, self.school)
        self.assertEqual(self.parent.status, "PENDING")
        self.assertEqual(self.parent.user.user_type, User.PARENT)

    def test_parent_str_representation(self):
        self.assertEqual(str(self.parent), "Test Parent - Parent")

    def test_parent_full_name_property(self):
        self.assertEqual(self.parent.full_name, "Test Parent")

    def test_parent_email_property(self):
        self.assertEqual(self.parent.email, "parent@test.com")

    def test_parent_active_children_property(self):
        self.assertEqual(self.parent.active_children.count(), 1)
        self.assertEqual(self.parent.active_children.first(), self.student)

    def test_parent_children_count_property(self):
        self.assertEqual(self.parent.children_count, 1)

    def test_parent_save_method_sets_user_type(self):
        new_user = User.objects.create_user(
            email="newparent@test.com", username="newparent", password="testpass"
        )
        new_parent = Parent.objects.create(
            user=new_user, school=self.school, phone_number="+254711111111"
        )
        new_user.refresh_from_db()
        self.assertEqual(new_user.user_type, User.PARENT)

    def test_parent_send_notification_method(self):
        notification = self.parent.send_notification(
            message="Test notification",
            notification_type="ACADEMIC",
            related_student=self.student,
            sender=self.admin,
        )
        self.assertEqual(notification.parent, self.parent)
        self.assertEqual(notification.message, "Test notification")
        self.assertEqual(notification.notification_type, "ACADEMIC")
        self.assertEqual(notification.related_student, self.student)
        self.assertEqual(notification.sent_by, self.admin)
        self.assertFalse(notification.is_read)


class ParentStatusChangeModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)

    def test_status_change_creation(self):
        status_change = ParentStatusChange.objects.create(
            parent=self.parent,
            changed_by=self.admin,
            from_status="PENDING",
            to_status="ACTIVE",
            reason="Approved by admin",
        )
        self.assertEqual(status_change.parent, self.parent)
        self.assertEqual(status_change.changed_by, self.admin)
        self.assertEqual(status_change.from_status, "PENDING")
        self.assertEqual(status_change.to_status, "ACTIVE")
        self.assertEqual(status_change.reason, "Approved by admin")

    def test_status_change_str_representation(self):
        status_change = ParentStatusChange.objects.create(
            parent=self.parent,
            changed_by=self.admin,
            from_status="PENDING",
            to_status="ACTIVE",
        )
        self.assertEqual(
            str(status_change),
            "Test Parent - Parent status changed from PENDING to ACTIVE",
        )


class ParentNotificationModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)

    def test_notification_creation(self):
        notification = ParentNotification.objects.create(
            parent=self.parent,
            message="Test notification",
            notification_type="ACADEMIC",
            related_student=self.student,
            sent_by=self.admin,
        )
        self.assertEqual(notification.parent, self.parent)
        self.assertEqual(notification.message, "Test notification")
        self.assertEqual(notification.notification_type, "ACADEMIC")
        self.assertEqual(notification.related_student, self.student)
        self.assertEqual(notification.sent_by, self.admin)
        self.assertFalse(notification.is_read)

    def test_notification_str_representation(self):
        notification = ParentNotification.objects.create(
            parent=self.parent,
            message="Test notification",
            notification_type="ACADEMIC",
        )
        self.assertEqual(str(notification), "Academic Update for Test Parent - Parent")


# python manage.py test skul_data.tests.parents_tests.test_parents_models
