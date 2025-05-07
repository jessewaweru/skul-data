from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.utils import timezone
from skul_data.tests.users_tests.users_factories import (
    UserFactory,
    SchoolFactory,
    RoleFactory,
    PermissionFactory,
    ParentFactory,
    TeacherFactory,
    SchoolAdminFactory,
    UserSessionFactory,
    ParentNotificationFactory,
    ParentStatusChangeFactory,
    TeacherWorkloadFactory,
    TeacherAttendanceFactory,
    TeacherDocumentFactory,
)
from skul_data.users.models.role import Role, Permission
from skul_data.users.models.base_user import User
from skul_data.users.models.parent import Parent
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.models.session import UserSession
from skul_data.students.models.student import Student
from django.db import IntegrityError

User = get_user_model()


class UserModelTest(TestCase):
    def setUp(self):
        # Create a user that will be the school admin
        self.admin_user = UserFactory(user_type=User.SCHOOL_ADMIN)

        # Create the school with that user as the admin
        self.school = SchoolFactory(schooladmin=self.admin_user)

        # Now create the SchoolAdmin profile that connects the user to the school
        self.admin = SchoolAdminFactory(user=self.admin_user, school=self.school)

        # Create other test objects
        self.user = UserFactory()
        self.role = RoleFactory(school=self.school)

    def test_user_creation(self):
        self.assertTrue(isinstance(self.user, User))
        self.assertEqual(self.user.__str__(), self.user.username)

    def test_user_type_choices(self):
        self.assertEqual(User.SCHOOL_ADMIN, "school_admin")
        self.assertEqual(User.TEACHER, "teacher")
        self.assertEqual(User.PARENT, "parent")
        self.assertEqual(User.OTHER, "other")

    def test_user_tag_uniqueness(self):
        user2 = UserFactory()
        self.assertNotEqual(self.user.user_tag, user2.user_tag)

    def test_user_has_perm(self):
        # Test with superuser
        self.user.user_type == User.SCHOOL_ADMIN = True
        self.assertTrue(self.user.has_perm("some_perm"))

        # Test with role permission
        self.user.user_type == User.SCHOOL_ADMIN = False
        permission = PermissionFactory(code="test_perm")  # Use code instead of codename
        self.role.permissions.add(permission)
        self.user.role = self.role
        self.assertTrue(self.user.has_perm("test_perm"))

        # Test without permission
        self.assertFalse(self.user.has_perm("nonexistent_perm"))


class RoleModelTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.role = RoleFactory(school=self.school)

    def test_role_creation(self):
        self.assertTrue(isinstance(self.role, Role))
        self.assertEqual(self.role.__str__(), f"{self.role.name} ({self.school.name})")

    def test_role_type_choices(self):
        self.assertEqual(Role.ROLE_TYPES[0], ("SYSTEM", "System Defined"))
        self.assertEqual(Role.ROLE_TYPES[1], ("CUSTOM", "Custom"))

    def test_unique_together_constraint(self):
        # Should be able to create role with same name in different school
        school2 = SchoolFactory()
        RoleFactory(name=self.role.name, school=school2)

        # Should not be able to create role with same name in same school
        with self.assertRaises(IntegrityError):
            RoleFactory(name=self.role.name, school=self.school)


class PermissionModelTest(TestCase):
    def setUp(self):
        self.permission = PermissionFactory()

    def test_permission_creation(self):
        self.assertTrue(isinstance(self.permission, Permission))
        self.assertEqual(
            self.permission.__str__(),
            f"{self.permission.name} ({self.permission.code})",
        )


class UserSessionModelTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.session = Session.objects.create(
            session_key="test_session_key",
            expire_date=timezone.now() + timezone.timedelta(days=1),
        )
        self.user_session = UserSessionFactory(user=self.user, session=self.session)

    def test_user_session_creation(self):
        self.assertTrue(isinstance(self.user_session, UserSession))
        self.assertEqual(
            self.user_session.__str__(),
            f"{self.user.username}'s session ({self.user_session.device or 'Unknown device'})",
        )

    def test_session_relationship(self):
        self.assertEqual(self.user_session.session, self.session)
        self.assertEqual(self.user_session.user, self.user)


class ParentModelTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.parent = ParentFactory(school=self.school)
        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth="2000-01-01",
            school=self.school,
        )

    def test_parent_creation(self):
        self.assertTrue(isinstance(self.parent, Parent))
        self.assertEqual(
            self.parent.__str__(), f"{self.parent.user.get_full_name()} - Parent"
        )

    def test_parent_user_type_set(self):
        self.assertEqual(self.parent.user.user_type, User.PARENT)

    def test_parent_children_relationship(self):
        self.parent.children.add(self.student)
        self.assertEqual(self.parent.children.count(), 1)
        self.assertEqual(self.parent.children.first(), self.student)

    def test_parent_notification_creation(self):
        notification = ParentNotificationFactory(parent=self.parent)
        self.assertEqual(notification.parent, self.parent)

    def test_parent_status_change(self):
        status_change = ParentStatusChangeFactory(parent=self.parent)
        self.assertEqual(status_change.parent, self.parent)
        self.assertEqual(status_change.from_status, "ACTIVE")
        self.assertEqual(status_change.to_status, "INACTIVE")


class TeacherModelTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.teacher = TeacherFactory(school=self.school)

    def test_teacher_creation(self):
        self.assertTrue(isinstance(self.teacher, Teacher))
        self.assertEqual(
            self.teacher.__str__(),
            f"{self.teacher.user.get_full_name()} - {self.school.name}",
        )

    def test_teacher_user_type_set(self):
        self.assertEqual(self.teacher.user.user_type, User.TEACHER)

    def test_teacher_workload(self):
        workload = TeacherWorkloadFactory(teacher=self.teacher)
        self.assertEqual(workload.teacher, self.teacher)

    def test_teacher_attendance(self):
        attendance = TeacherAttendanceFactory(teacher=self.teacher)
        self.assertEqual(attendance.teacher, self.teacher)

    def test_teacher_document(self):
        document = TeacherDocumentFactory(teacher=self.teacher)
        self.assertEqual(document.teacher, self.teacher)


class SchoolAdminModelTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = SchoolAdminFactory(school=self.school)

    def test_school_admin_creation(self):
        self.assertTrue(isinstance(self.admin, SchoolAdmin))
        self.assertEqual(
            self.admin.__str__(),
            f"{self.admin.user.get_full_name()} - {self.school.name}",
        )

    def test_school_admin_user_type_set(self):
        self.assertEqual(self.admin.user.user_type, User.SCHOOL_ADMIN)

    def test_primary_admin_constraint(self):
        # Creating a new primary admin should demote existing one
        admin2 = SchoolAdminFactory(school=self.school, is_primary=True)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_primary)
        self.assertTrue(admin2.is_primary)


# python manage.py test skul_data.tests.users_tests.test_users_models
