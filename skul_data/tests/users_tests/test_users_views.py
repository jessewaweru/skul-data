from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework import status
from skul_data.tests.users_tests.users_factories import (
    UserFactory,
    SchoolFactory,
    RoleFactory,
    PermissionFactory,
    ParentFactory,
    TeacherFactory,
    SchoolAdminFactory,
    ParentNotificationFactory,
    UserSessionFactory,
)
from skul_data.users.models.role import Role, Permission
from skul_data.users.models.session import UserSession
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Subject, Student
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.school_admin import SchoolAdmin
from django.utils import timezone
from django.contrib.sessions.models import Session


User = get_user_model()


class RoleViewSetTest(APITestCase):

    def setUp(self):
        self.school = SchoolFactory()
        self.admin = SchoolAdminFactory(school=self.school)
        self.admin.user.is_staff = True  # Add this
        self.admin.user.school = self.school
        self.admin.user.save()  # Add this
        self.client.force_authenticate(user=self.admin.user)
        # Create permission and assign to role
        self.permission = PermissionFactory(
            code="manage_roles"
        )  # Or whatever permission your view requires
        self.role = RoleFactory(school=self.school)
        self.role.permissions.add(self.permission)
        self.admin.user.role = self.role  # Assign role to user
        self.admin.user.save()
        self.url = reverse("role-list")

    def test_list_roles(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        if "results" in response.data:  # Paginated response
            self.assertEqual(len(response.data["results"]), 1)
        else:  # Non-paginated
            self.assertEqual(len(response.data), 1)

    def test_create_role(self):
        data = {
            "name": "New Role",
            "permissions": [self.permission.id],
            "school": self.school.id,  # Add the school ID
        }
        response = self.client.post(self.url, data, format="json")
        print(f"Response data: {response.data}")  # For debugging
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Role.objects.count(), 2)

    def test_update_role(self):
        url = reverse("role-detail", args=[self.role.id])
        data = {
            "name": "Updated Role",
            "permissions": [self.permission.id],
            "school": self.school.id,  # Add the school ID
        }
        response = self.client.put(url, data, format="json")
        print(f"Response data: {response.data}")  # For debugging
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.role.refresh_from_db()
        self.assertEqual(self.role.name, "Updated Role")

    def test_delete_role(self):
        url = reverse("role-detail", args=[self.role.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Role.objects.count(), 0)


class SessionViewSetTest(APITestCase):
    def setUp(self):
        self.admin = SchoolAdminFactory()
        self.client.force_authenticate(user=self.admin.user)

        # Create a real Django session
        session = Session.objects.create(
            session_key="test_session_key",
            expire_date=timezone.now() + timezone.timedelta(days=1),
            session_data="{}",  # Avoid null issue
        )

        # Pass session object, not session_key
        self.user_session = UserSessionFactory(
            user=self.admin.user, session=session  # ✅ Correct usage
        )

        self.url = reverse("usersession-list")

    def test_list_sessions(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_session(self):
        url = reverse(
            "usersession-detail", args=[self.user_session.session.session_key]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["session_key"], self.user_session.session.session_key
        )

    def test_delete_session(self):
        url = reverse(
            "usersession-detail", args=[self.user_session.session.session_key]
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(UserSession.objects.count(), 0)


class ParentViewSetTest(APITestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = SchoolAdminFactory(school=self.school)

        # IMPORTANT: Set the correct user_type for the SchoolAdmin user
        self.admin.user.user_type = User.SCHOOL_ADMIN
        self.admin.user.save()

        # Create role with the necessary permissions
        self.role = RoleFactory(school=self.school)

        # Create and add ALL relevant permissions for parent management
        permission_codes = [
            "manage_parents",
            "create_parent",
            "update_parent",
            "view_parents",
            "assign_children",
            "change_parent_status",
        ]

        for code in permission_codes:
            perm = PermissionFactory(code=code)
            self.role.permissions.add(perm)

        # Assign role to admin user
        self.admin.user.role = self.role
        self.admin.user.school = self.school
        self.admin.user.save()

        # Authenticate the client
        self.client.force_authenticate(user=self.admin.user)

        # Create test data
        self.parent = ParentFactory(school=self.school)
        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth="2000-01-01",
            school=self.school,
        )
        self.url = reverse("parent-list")

    def test_list_parents(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertEqual(len(response.data["results"]), 1)
        if "results" in response.data:  # Paginated response
            self.assertEqual(len(response.data["results"]), 1)
        else:  # Non-paginated
            self.assertEqual(len(response.data), 1)

    def test_create_parent(self):
        data = {
            "email": "newparent@example.com",
            "first_name": "New",
            "last_name": "Parent",
            "phone_number": "1234567890",
            "school": self.school.id,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Parent.objects.count(), 2)

    def test_change_parent_status(self):
        url = reverse("parent-change-status", args=[self.parent.id])
        data = {
            "status": "INACTIVE",
            "reason": "Test reason",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.status, "INACTIVE")

    def test_assign_children(self):
        url = reverse("parent-assign-children", args=[self.parent.id])
        data = {
            "student_ids": [self.student.id],
            "action": "ADD",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.parent.children.count(), 1)

    def test_parent_notifications(self):
        ParentNotificationFactory(parent=self.parent)
        url = reverse("parent-notifications", args=[self.parent.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TeacherViewSetTest(APITestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = SchoolAdminFactory(school=self.school)

        # Make sure admin is properly configured
        self.admin.user.is_staff = True
        self.admin.user.user_type = User.SCHOOL_ADMIN  # Make sure this is set properly

        # Create role with the necessary permissions
        self.role = RoleFactory(school=self.school)

        # Add ALL needed permissions explicitly
        permission_codes = [
            "manage_teachers",
            "create_teacher",
            "update_teacher",
            "view_teachers",
            "assign_subjects",
            "assign_classes",
            "change_teacher_status",
        ]

        for code in permission_codes:
            perm = PermissionFactory(code=code)
            self.role.permissions.add(perm)

        # Assign role to admin user
        self.admin.user.role = self.role
        self.admin.user.school = self.school
        self.admin.user.save()

        # Authenticate the client
        self.client.force_authenticate(user=self.admin.user)

        # Create test data
        self.teacher = TeacherFactory(school=self.school)
        self.subject = Subject.objects.create(name="Math", school=self.school)
        self.url = reverse("teacher-list")

    def test_list_teachers(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        if "results" in response.data:  # Paginated response
            self.assertEqual(len(response.data["results"]), 1)
        else:  # Non-paginated
            self.assertEqual(len(response.data), 1)

    def test_create_teacher(self):
        user = UserFactory()
        data = {
            "user_id": user.id,
            "school": self.school.id,
            "status": "ACTIVE",
        }
        response = self.client.post(self.url, data, format="json")

        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")  # This will show the validation errors

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Teacher.objects.count(), 2)

    def test_change_teacher_status(self):
        url = reverse("teacher-change-status", args=[self.teacher.id])
        data = {
            "status": "TERMINATED",
            "termination_date": "2023-12-31",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.status, "TERMINATED")

    def test_assign_subjects(self):
        url = reverse("teacher-assign-subjects", args=[self.teacher.id])
        data = {
            "subject_ids": [self.subject.id],
            "action": "ADD",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.teacher.subjects_taught.count(), 1)


class SchoolAdminViewSetTest(APITestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.primary_admin = SchoolAdminFactory(school=self.school, is_primary=True)

        # Make user staff for full permissions
        self.primary_admin.user.is_staff = True

        # Add role and permissions
        self.role = RoleFactory(school=self.school)
        self.primary_admin.user.role = self.role

        # Add manage_admins permission
        permission_codes = ["manage_admins", "update_admin", "manage_school"]
        for code in permission_codes:
            permission = PermissionFactory(code=code)
            self.role.permissions.add(permission)

        self.primary_admin.user.school = self.school
        self.primary_admin.user.save()

        self.client.force_authenticate(user=self.primary_admin.user)
        self.admin = SchoolAdminFactory(school=self.school, is_primary=False)
        self.url = reverse("school-admin-list")

    def test_list_admins(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        if "results" in response.data:  # Paginated response
            self.assertEqual(len(response.data["results"]), 2)
        else:  # Non-paginated
            self.assertEqual(len(response.data), 2)

    def test_create_admin(self):
        data = {
            "email": "newadmin@example.com",
            "first_name": "New",
            "last_name": "Admin",
            "school": self.school.id,
            "is_primary": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SchoolAdmin.objects.count(), 3)

    def test_make_primary_admin(self):
        url = reverse("school-admin-detail", args=[self.admin.id])
        data = {"is_primary": True}

        # Make the request to change primary status
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh both admins from the database
        self.admin.refresh_from_db()
        self.primary_admin.refresh_from_db()

        # Check that the status was transferred correctly
        self.assertTrue(self.admin.is_primary)
        self.assertFalse(self.primary_admin.is_primary)


# python manage.py test skul_data.tests.users_tests.test_users_views
