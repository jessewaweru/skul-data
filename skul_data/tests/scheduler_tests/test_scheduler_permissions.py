from django.test import TestCase, RequestFactory
from django.contrib.auth.models import AnonymousUser
from skul_data.users.models import User
from skul_data.schools.models.school import School
from skul_data.scheduler.models.scheduler import SchoolEvent
from skul_data.scheduler.views.scheduler import SchoolEventDetailView
from skul_data.users.permissions.permission import CanManageEvent


class SchedulerPermissionsTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        # Create users
        self.admin = User.objects.create_user(
            email="admin@school.com",
            password="adminpass",
            user_type=User.SCHOOL_ADMIN,
            first_name="Admin",
            last_name="User",
        )

        self.teacher = User.objects.create_user(
            email="teacher@school.com",
            password="teacherpass",
            user_type=User.TEACHER,
            first_name="Teacher",
            last_name="User",
        )

        self.parent = User.objects.create_user(
            email="parent@school.com",
            password="parentpass",
            user_type=User.PARENT,
            first_name="Parent",
            last_name="User",
        )

        # Create school
        self.school = School.objects.create(
            name="Test School", email="test@school.com", schooladmin=self.admin
        )

        # Create event
        self.event = SchoolEvent.objects.create(
            title="Test Event",
            start_datetime="2023-01-01T09:00:00Z",
            end_datetime="2023-01-01T11:00:00Z",
            created_by=self.admin,
            school=self.school,
        )

    def test_can_manage_event_permission(self):
        permission = CanManageEvent()
        request = self.factory.get("/")
        request.method = "PUT"  # Test with unsafe method

        # Admin should have permission
        request.user = self.admin
        self.assertTrue(permission.has_object_permission(request, None, self.event))

        # Teacher should not have permission
        request.user = self.teacher
        self.assertFalse(
            permission.has_object_permission(request, None, self.event),
            "Teacher should not have permission to manage events",
        )

        # Parent should not have permission
        request.user = self.parent
        self.assertFalse(
            permission.has_object_permission(request, None, self.event),
            "Parent should not have permission to manage events",
        )

        # Anonymous user should not have permission
        request.user = AnonymousUser()
        self.assertFalse(
            permission.has_object_permission(request, None, self.event),
            "Anonymous user should not have permission",
        )

        # Verify safe methods (GET) are allowed for all authenticated users
        request.method = "GET"
        request.user = self.teacher
        self.assertTrue(
            permission.has_object_permission(request, None, self.event),
            "Teachers should have read-only access",
        )

    def test_school_event_detail_view_permissions(self):
        # GET should be allowed for any authenticated user
        request = self.factory.get("/")
        request.user = self.teacher
        view = SchoolEventDetailView()
        view.request = request
        permissions = view.get_permissions()
        self.assertTrue(permissions[0].has_permission(request, view))
        self.assertTrue(permissions[0].has_object_permission(request, view, self.event))

        # PUT/PATCH/DELETE should require CanManageEvent (teacher shouldn't have this)
        request.method = "PUT"
        view = SchoolEventDetailView()
        view.request = request
        permissions = view.get_permissions()

        # Debug print
        print(
            f"PUT request by teacher - has_permission: {permissions[0].has_permission(request, view)}"
        )
        print(
            f"PUT request by teacher - has_object_permission: {permissions[0].has_object_permission(request, view, self.event)}"
        )

        # Teacher should not have general permission for PUT
        self.assertFalse(permissions[0].has_permission(request, view))

        # Also verify they don't have object permission
        self.assertFalse(
            permissions[0].has_object_permission(request, view, self.event)
        )

        # Admin should have permission for PUT/PATCH/DELETE
        request.user = self.admin
        view = SchoolEventDetailView()
        view.request = request
        permissions = view.get_permissions()
        self.assertTrue(permissions[0].has_permission(request, view))
        self.assertTrue(permissions[0].has_object_permission(request, view, self.event))


# python manage.py test skul_data.tests.scheduler_tests.test_scheduler_permissions
