# tests/permissions/test_timetable_permissions.py
from rest_framework.test import APIRequestFactory
from django.test import TestCase
from skul_data.tests.school_timetables_tests.test_helpers import (
    create_test_school,
    create_test_user,
)
from skul_data.users.models.base_user import User
from skul_data.users.permissions.permission import HasRolePermission
from skul_data.school_timetables.views.school_timetable import (
    TimeSlotViewSet,
    TimetableViewSet,
    LessonViewSet,
)


class TimetablePermissionsTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.school, _ = create_test_school()

        # Create view instances
        self.timeslot_view = TimeSlotViewSet()
        self.timetable_view = TimetableViewSet()
        self.lesson_view = LessonViewSet()

        # Set required permissions on views
        self.timeslot_view.required_permission = "manage_timetable_settings"
        self.timetable_view.required_permission_get = "view_timetables"
        self.timetable_view.required_permission_post = "manage_timetables"
        self.lesson_view.required_permission_get = "view_timetables"
        self.lesson_view.required_permission_post = "manage_timetables"

    def test_school_admin_has_full_access(self):
        # Create school admin user
        admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.SCHOOL_ADMIN,
            school=self.school,
        )

        # Test TimeSlotViewSet
        request = self.factory.get("/timeslots/")
        request.user = admin_user
        self.timeslot_view.request = request
        self.assertTrue(HasRolePermission().has_permission(request, self.timeslot_view))

        # Test TimetableViewSet
        request = self.factory.get("/timetables/")
        request.user = admin_user
        self.timetable_view.request = request
        self.assertTrue(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

        request = self.factory.post("/timetables/", {})
        request.user = admin_user
        self.timetable_view.request = request
        self.assertTrue(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

    def test_teacher_with_permissions(self):
        # Create teacher user with view permissions
        teacher_user = create_test_user(
            email="teacher@test.com",
            user_type=User.TEACHER,
            school=self.school,
            role_permissions=["view_timetables"],
        )

        # Should have view access but not manage
        request = self.factory.get("/timetables/")
        request.user = teacher_user
        self.timetable_view.request = request
        self.assertTrue(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

        request = self.factory.post("/timetables/", {})
        request.user = teacher_user
        self.timetable_view.request = request
        self.assertFalse(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

    def test_teacher_without_permissions(self):
        # Create teacher user without permissions
        teacher_user = create_test_user(
            email="teacher@test.com",
            user_type=User.TEACHER,
            school=self.school,
            role_permissions=[],
        )

        # Should not have any access
        request = self.factory.get("/timetables/")
        request.user = teacher_user
        self.timetable_view.request = request
        self.assertFalse(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

    def test_parent_access(self):
        # Parent should not have access to timetable management
        parent_user = create_test_user(
            email="parent@test.com",
            user_type=User.PARENT,
            school=self.school,
        )

        request = self.factory.get("/timetables/")
        request.user = parent_user
        self.timetable_view.request = request
        self.assertFalse(
            HasRolePermission().has_permission(request, self.timetable_view)
        )


class AdministratorTimetablePermissionsTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.school, _ = create_test_school()

        # Create view instances
        self.timeslot_view = TimeSlotViewSet()
        self.timetable_view = TimetableViewSet()
        self.lesson_view = LessonViewSet()

        # Set required permissions on views
        self.timeslot_view.required_permission = "manage_timetable_settings"
        self.timetable_view.required_permission_get = "view_timetables"
        self.timetable_view.required_permission_post = "manage_timetables"
        self.lesson_view.required_permission_get = "view_timetables"
        self.lesson_view.required_permission_post = "manage_timetables"

    def test_administrator_with_timetable_permissions(self):
        """Test that administrators with timetable permissions have proper access"""
        # Create administrator user with timetable permissions
        admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.ADMINISTRATOR,
            school=self.school,
            role_permissions=[
                "manage_timetables",
                "view_timetables",
                "manage_timetable_settings",
            ],
        )

        # Create administrator profile with elevated access
        from skul_data.users.models.school_admin import AdministratorProfile

        AdministratorProfile.objects.create(
            user=admin_user,
            school=self.school,
            position="Timetable Administrator",
            access_level="elevated",
            permissions_granted=[
                "manage_timetables",
                "view_timetables",
                "manage_timetable_settings",
            ],
        )

        # Test TimeSlotViewSet access
        request = self.factory.get("/timeslots/")
        request.user = admin_user
        self.timeslot_view.request = request
        self.assertTrue(HasRolePermission().has_permission(request, self.timeslot_view))

        # Test TimetableViewSet GET access
        request = self.factory.get("/timetables/")
        request.user = admin_user
        self.timetable_view.request = request
        self.assertTrue(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

        # Test TimetableViewSet POST access
        request = self.factory.post("/timetables/", {})
        request.user = admin_user
        self.timetable_view.request = request
        self.assertTrue(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

    def test_administrator_without_timetable_permissions(self):
        """Test that administrators without timetable permissions are restricted"""
        # Create administrator user without timetable permissions
        admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.ADMINISTRATOR,
            school=self.school,
            role_permissions=["manage_users"],  # Different permission
        )

        # Create administrator profile with standard access
        from skul_data.users.models.school_admin import AdministratorProfile

        AdministratorProfile.objects.create(
            user=admin_user,
            school=self.school,
            position="General Administrator",
            access_level="standard",
            permissions_granted=["manage_users"],
        )

        # Test TimeSlotViewSet access (should fail)
        request = self.factory.get("/timeslots/")
        request.user = admin_user
        self.timeslot_view.request = request
        self.assertFalse(
            HasRolePermission().has_permission(request, self.timeslot_view)
        )

        # Test TimetableViewSet GET access (should fail)
        request = self.factory.get("/timetables/")
        request.user = admin_user
        self.timetable_view.request = request
        self.assertFalse(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

    def test_administrator_with_direct_permissions_granted(self):
        """Test that administrators with directly granted permissions have access"""
        # Create administrator user without role permissions
        admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.ADMINISTRATOR,
            school=self.school,
        )

        # Create administrator profile with directly granted permissions
        from skul_data.users.models.school_admin import AdministratorProfile

        AdministratorProfile.objects.create(
            user=admin_user,
            school=self.school,
            position="Timetable Admin",
            access_level="elevated",
            permissions_granted=["manage_timetables", "view_timetables"],
        )

        # Test TimetableViewSet GET access (should pass)
        request = self.factory.get("/timetables/")
        request.user = admin_user
        self.timetable_view.request = request
        self.assertTrue(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

        # Test TimetableViewSet POST access (should pass)
        request = self.factory.post("/timetables/", {})
        request.user = admin_user
        self.timetable_view.request = request
        self.assertTrue(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

    def test_restricted_administrator_access(self):
        """Test that administrators with restricted access can't manage timetables"""
        # Create administrator user with restricted access
        admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.ADMINISTRATOR,
            school=self.school,
        )

        # Create restricted administrator profile
        from skul_data.users.models.school_admin import AdministratorProfile

        AdministratorProfile.objects.create(
            user=admin_user,
            school=self.school,
            position="Restricted Admin",
            access_level="restricted",
            permissions_granted=["view_timetables"],  # Only view permission
        )

        # Test TimeSlotViewSet access (should fail - needs manage_timetable_settings)
        request = self.factory.get("/timeslots/")
        request.user = admin_user
        self.timeslot_view.request = request
        self.assertFalse(
            HasRolePermission().has_permission(request, self.timeslot_view)
        )

        # Test TimetableViewSet GET access (should pass)
        request = self.factory.get("/timetables/")
        request.user = admin_user
        self.timetable_view.request = request
        self.assertTrue(
            HasRolePermission().has_permission(request, self.timetable_view)
        )

        # Test TimetableViewSet POST access (should fail)
        request = self.factory.post("/timetables/", {})
        request.user = admin_user
        self.timetable_view.request = request
        self.assertFalse(
            HasRolePermission().has_permission(request, self.timetable_view)
        )


# python manage.py test skul_data.tests.school_timetables_tests.test_school_timetables_permissions
