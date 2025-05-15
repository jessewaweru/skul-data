from django.test import TestCase, RequestFactory
from rest_framework.permissions import SAFE_METHODS
from skul_data.users.models.role import Role, Permission
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.users.permissions.permission import (
    IsAdministrator,
    IsTeacher,
    HasRolePermission,
)
from skul_data.users.views.teacher import TeacherViewSet
from skul_data.tests.teachers_tests.test_helpers import create_test_school


class TeacherPermissionsTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.school, self.admin = create_test_school()

        # Create a teacher user
        self.teacher_user = User.objects.create_user(
            email="teacher@test.com",
            username="teacher",
            password="testpass",
            user_type=User.TEACHER,
        )

        # Create a role with teacher permissions
        self.teacher_role = Role.objects.create(
            name="Class Teacher",
            school=self.school,
            role_type="CUSTOM",
        )

        # Add teacher-specific permissions
        teacher_permissions = [
            ("view_teacher_profile", "View teacher profile"),
            ("manage_attendance", "Manage attendance"),
        ]

        for code, name in teacher_permissions:
            perm, _ = Permission.objects.get_or_create(code=code, name=name)
            self.teacher_role.permissions.add(perm)

        self.teacher_user.role = self.teacher_role
        self.teacher_user.save()

        # Create a teacher profile
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, school=self.school
        )

    def test_is_administrator_permission(self):
        permission = IsAdministrator()
        request = self.factory.get("/")
        request.user = self.admin

        self.assertTrue(permission.has_permission(request, None))

        request.user = self.teacher_user
        self.assertFalse(permission.has_permission(request, None))

    def test_is_teacher_permission(self):
        permission = IsTeacher()
        request = self.factory.get("/")
        request.user = self.teacher_user

        self.assertTrue(permission.has_permission(request, None))

        request.user = self.admin
        self.assertFalse(permission.has_permission(request, None))

    def test_has_role_permission(self):
        permission = HasRolePermission()
        view = TeacherViewSet()
        view.action = "list"
        view.required_permission = "view_teacher_profile"

        # Teacher with correct permission
        request = self.factory.get("/")
        request.user = self.teacher_user
        self.assertTrue(permission.has_permission(request, view))

        # Admin always has permission
        request.user = self.admin
        self.assertTrue(permission.has_permission(request, view))

        # User without permission
        new_user = User.objects.create_user(
            email="noaccess@test.com",
            username="noaccess",
            password="testpass",
            user_type=User.TEACHER,
        )
        request.user = new_user
        self.assertFalse(permission.has_permission(request, view))

    # def test_has_object_permission(self):
    #     permission = HasRolePermission()
    #     view = TeacherViewSet()
    #     view.action = "retrieve"
    #     view.required_permission = "view_teacher_profile"
    #     view.owner_field = "user"

    #     # Teacher viewing their own profile
    #     request = self.factory.get("/")
    #     request.user = self.teacher_user
    #     self.assertTrue(permission.has_object_permission(request, view, self.teacher))

    #     # Admin viewing any profile
    #     request.user = self.admin
    #     self.assertTrue(permission.has_object_permission(request, view, self.teacher))

    #     # Other teacher viewing someone else's profile
    #     other_teacher = User.objects.create_user(
    #         email="other@test.com",
    #         username="other",
    #         password="testpass",
    #         user_type=User.TEACHER,
    #     )
    #     request.user = other_teacher
    #     self.assertFalse(permission.has_object_permission(request, view, self.teacher))

    def test_has_object_permission(self):
        permission = HasRolePermission()
        view = TeacherViewSet()
        view.action = "retrieve"
        view.required_permission = "view_teacher_profile"
        view.owner_field = "user"

        # Teacher viewing their own profile
        request = self.factory.get("/")
        request.user = self.teacher_user
        self.assertTrue(permission.has_object_permission(request, view, self.teacher))

        # Admin viewing any profile
        request.user = self.admin
        self.assertTrue(permission.has_object_permission(request, view, self.teacher))

        # Other teacher viewing someone else's profile (should fail)
        other_teacher_user = User.objects.create_user(
            email="other@test.com",
            username="other",
            password="testpass",
            user_type=User.TEACHER,
        )
        # Ensure this user has no role/permissions
        other_teacher_user.role = None
        other_teacher_user.save()

        request.user = other_teacher_user
        self.assertFalse(permission.has_object_permission(request, view, self.teacher))


# python manage.py test skul_data.tests.teachers_tests.test_teachers_permissions
