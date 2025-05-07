from django.test import TestCase
from skul_data.tests.users_tests.users_factories import (
    UserFactory,
    SchoolFactory,
    RoleFactory,
    PermissionFactory,
    ParentFactory,
    TeacherFactory,
    SchoolAdminFactory,
    ParentNotificationFactory,
    TeacherWorkloadFactory,
    TeacherAttendanceFactory,
    TeacherDocumentFactory,
)
from skul_data.users.models.base_user import User
from skul_data.users.serializers.base_user import (
    BaseUserSerializer,
    UserDetailSerializer,
    RoleSerializer,
)
from skul_data.students.models.student import Student
from skul_data.users.serializers.parent import (
    ParentSerializer,
    ParentCreateSerializer,
    ParentChildAssignmentSerializer,
    ParentNotificationPreferenceSerializer,
    ParentNotificationSerializer,
    ParentStatusChangeSerializer,
)
from skul_data.users.serializers.teacher import (
    TeacherSerializer,
    TeacherCreateSerializer,
    TeacherStatusChangeSerializer,
    TeacherAssignmentSerializer,
    TeacherSubjectAssignmentSerializer,
    TeacherWorkloadSerializer,
    TeacherAttendanceSerializer,
    TeacherDocumentSerializer,
)
from skul_data.users.serializers.school_admin import (
    SchoolAdminSerializer,
    SchoolAdminCreateSerializer,
)


class BaseUserSerializerTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.role = RoleFactory()
        self.data = {
            "username": "testuser",
            "email": "test@example.com",
            "user_type": User.PARENT,
            "role_id": self.role.id,
        }

    def test_base_user_serializer(self):
        serializer = BaseUserSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")

    def test_user_detail_serializer(self):
        parent = ParentFactory(user=self.user)
        serializer = UserDetailSerializer(self.user)
        data = serializer.data
        self.assertIn("teacher_profile", data)
        self.assertIn("parent_profile", data)
        self.assertIn("schooladmin_profile", data)


class RoleSerializerTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.permission = PermissionFactory()
        self.data = {
            "name": "Test Role",
            "role_type": "CUSTOM",
            "permissions": [self.permission.id],
            "school": self.school.id,
        }

    def test_role_serializer_create(self):
        serializer = RoleSerializer(
            data={
                "name": "Test Role",
                "role_type": "CUSTOM",
                "permissions": [self.permission.id],
                "school": self.school.id,  # Make sure school is included
            }
        )
        self.assertTrue(
            serializer.is_valid(), serializer.errors
        )  # Check validation errors
        role = serializer.save()
        self.assertEqual(role.name, "Test Role")
        self.assertEqual(role.permissions.count(), 1)

    def test_role_serializer_update(self):
        role = RoleFactory(school=self.school)
        serializer = RoleSerializer(instance=role, data=self.data)
        self.assertTrue(serializer.is_valid())
        updated_role = serializer.save()
        self.assertEqual(updated_role.permissions.count(), 1)


class ParentSerializerTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.parent = ParentFactory(school=self.school)
        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth="2000-01-01",
            school=self.school,
        )
        self.data = {
            "email": "parent@example.com",
            "first_name": "Parent",
            "last_name": "User",
            "phone_number": "1234567890",
            "school": self.school.id,
            "children": [self.student.id],
        }

    def test_parent_serializer(self):
        serializer = ParentSerializer(instance=self.parent)
        data = serializer.data
        self.assertIn("username", data)
        self.assertIn("email", data)
        self.assertIn("children_details", data)

    def test_parent_create_serializer(self):
        serializer = ParentCreateSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        parent = serializer.save()
        self.assertEqual(parent.user.email, "parent@example.com")
        self.assertEqual(parent.user.user_type, User.PARENT)

    def test_parent_child_assignment_serializer(self):
        data = {
            "student_ids": [self.student.id],
            "action": "ADD",
        }
        serializer = ParentChildAssignmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_parent_notification_preference_serializer(self):
        data = {
            "receive_email_notifications": False,
            "preferred_language": "sw",
        }
        serializer = ParentNotificationPreferenceSerializer(
            instance=self.parent, data=data
        )
        self.assertTrue(serializer.is_valid())
        updated_parent = serializer.save()
        self.assertFalse(updated_parent.receive_email_notifications)

    def test_parent_notification_serializer(self):
        notification = ParentNotificationFactory(parent=self.parent)
        serializer = ParentNotificationSerializer(notification)
        data = serializer.data
        self.assertIn("message", data)
        self.assertIn("notification_type", data)

    def test_parent_status_change_serializer(self):
        data = {
            "status": "INACTIVE",
            "reason": "Test reason",
        }
        serializer = ParentStatusChangeSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class TeacherSerializerTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.teacher = TeacherFactory(school=self.school)
        self.data = {
            "user_id": self.teacher.user.id,
            "school": self.school.id,
            "status": "ACTIVE",
            "hire_date": "2023-01-01",
        }

    def test_teacher_serializer(self):
        serializer = TeacherSerializer(instance=self.teacher)
        data = serializer.data
        self.assertIn("username", data)
        self.assertIn("email", data)
        self.assertIn("subjects_taught", data)

    def test_teacher_create_serializer(self):
        user = UserFactory(user_type=User.TEACHER)
        serializer = TeacherCreateSerializer(
            data={
                "user_id": user.id,
                "school": self.school.id,
                "status": "ACTIVE",
                "hire_date": "2023-01-01",
                "qualification": "B.Ed",
                "specialization": "Mathematics",
                "years_of_experience": 5,
                "phone_number": "1234567890",  # Add if required
            }
        )
        self.assertTrue(
            serializer.is_valid(), serializer.errors
        )  # Print errors if not valid
        teacher = serializer.save()
        self.assertEqual(teacher.user.user_type, User.TEACHER)

    def test_teacher_status_change_serializer(self):
        data = {
            "status": "TERMINATED",
            "termination_date": "2023-12-31",
        }
        serializer = TeacherStatusChangeSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_teacher_assignment_serializer(self):
        data = {
            "class_ids": [],
            "action": "REPLACE",
        }
        serializer = TeacherAssignmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_teacher_subject_assignment_serializer(self):
        data = {
            "subject_ids": [],
            "action": "REPLACE",
        }
        serializer = TeacherSubjectAssignmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_teacher_workload_serializer(self):
        workload = TeacherWorkloadFactory(teacher=self.teacher)
        serializer = TeacherWorkloadSerializer(workload)
        data = serializer.data
        self.assertIn("teacher", data)
        self.assertIn("school_class", data)

    def test_teacher_attendance_serializer(self):
        attendance = TeacherAttendanceFactory(teacher=self.teacher)
        serializer = TeacherAttendanceSerializer(attendance)
        data = serializer.data
        self.assertIn("teacher", data)
        self.assertIn("recorded_by", data)

    def test_teacher_document_serializer(self):
        document = TeacherDocumentFactory(teacher=self.teacher)
        serializer = TeacherDocumentSerializer(document)
        data = serializer.data
        self.assertIn("teacher", data)
        self.assertIn("uploaded_by", data)


class SchoolAdminSerializerTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = SchoolAdminFactory(school=self.school)
        self.data = {
            "email": "admin@example.com",
            "first_name": "Admin",
            "last_name": "User",
            "school": self.school.id,
            "is_primary": True,
        }

    def test_school_admin_serializer(self):
        serializer = SchoolAdminSerializer(instance=self.admin)
        data = serializer.data
        self.assertIn("user_details", data)
        self.assertIn("school_name", data)

    def test_school_admin_create_serializer(self):
        serializer = SchoolAdminCreateSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        admin = serializer.save()
        self.assertEqual(admin.user.email, "admin@example.com")
        self.assertEqual(admin.user.user_type, User.SCHOOL_ADMIN)


# python manage.py test skul_data.tests.users_tests.test_users_serializers
