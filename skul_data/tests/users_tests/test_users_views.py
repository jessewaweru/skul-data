from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from skul_data.tests.users_tests.users_factories import (
    SchoolFactory,
    RoleFactory,
    PermissionFactory,
    SchoolAdminFactory,
    UserSessionFactory,
    TeacherFactory,
    ParentFactory,
)
from skul_data.users.models.role import Role
from skul_data.users.models.session import UserSession
from skul_data.users.models.school_admin import SchoolAdmin
from django.utils import timezone
from django.contrib.sessions.models import Session


User = get_user_model()


class RoleViewSetTest(APITestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.primary_admin = SchoolAdminFactory(school=self.school, is_primary=True)
        self.primary_admin.user.is_staff = True
        self.primary_admin.user.save()

        # Create role with manage_users permission
        self.role = RoleFactory(school=self.school)
        self.permission = PermissionFactory(code="manage_users")
        self.role.permissions.add(self.permission)
        self.primary_admin.user.role = self.role
        self.primary_admin.user.save()

        # Create test users
        self.teacher = TeacherFactory(school=self.school)
        self.parent = ParentFactory(school=self.school)

        self.client.force_authenticate(user=self.primary_admin.user)
        self.url = reverse("user-list")

        # Delete any automatically created roles
        Role.objects.filter(school=self.school).exclude(id=self.role.id).delete()

    def test_list_roles(self):
        # Debug: Print all roles in database
        all_roles = Role.objects.all()
        print(f"All roles in DB: {list(all_roles.values_list('name', 'school'))}")

        # Debug: Print roles filtered by school
        filtered_roles = Role.objects.filter(school=self.school)
        print(
            f"Roles for school {self.school.id}: {list(filtered_roles.values_list('name'))}"
        )

        response = self.client.get(reverse("role-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Debug: Print response data
        print(f"Response data: {response.data}")

        if "results" in response.data:
            self.assertEqual(len(response.data["results"]), 1)
        else:
            self.assertEqual(len(response.data), 1)

    def test_create_role(self):
        self.url = reverse("role-list")  # Make sure this is the role endpoint
        data = {
            "name": "New Role",
            "permissions": [self.permission.id],
            "school": self.school.id,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

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
        initial_count = Role.objects.count()
        print(f"Initial role count: {initial_count}")

        url = reverse("role-detail", args=[self.role.id])
        response = self.client.delete(url)

        print(f"Delete response status: {response.status_code}")
        print(f"Response content: {response.content}")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Role.objects.count(), initial_count - 1)

        # Verify the specific role is gone
        with self.assertRaises(Role.DoesNotExist):
            Role.objects.get(id=self.role.id)


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
        self.user_session = UserSessionFactory(user=self.admin.user, session=session)

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


class UserViewSetTest(APITestCase):
    def setUp(self):
        # Create school and primary admin
        self.school = SchoolFactory()
        self.primary_admin = SchoolAdminFactory(school=self.school, is_primary=True)
        self.primary_admin.user.is_staff = True

        # Create role with manage_users permission
        self.role = RoleFactory(school=self.school)
        self.permission = PermissionFactory(code="manage_users")
        self.role.permissions.add(self.permission)
        self.primary_admin.user.role = self.role
        self.primary_admin.user.save()

        # Create test users
        self.teacher = TeacherFactory(school=self.school)
        self.parent = ParentFactory(school=self.school)

        # Authenticate as primary admin
        self.client.force_authenticate(user=self.primary_admin.user)

        # Base URL
        self.url = reverse("user-list")

    def test_list_users(self):
        """School admin should see all users in their school"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should see admin, teacher, and parent
        user_ids = (
            [user["id"] for user in response.data["results"]]
            if "results" in response.data
            else [user["id"] for user in response.data]
        )
        self.assertIn(self.primary_admin.user.id, user_ids)
        self.assertIn(self.teacher.user.id, user_ids)
        self.assertIn(self.parent.user.id, user_ids)

    def test_create_user(self):
        """School admin should be able to create new users"""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "testpassword123",
            "is_active": True,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_retrieve_user_detail(self):
        """Should return detailed user information"""
        url = reverse("user-detail", args=[self.teacher.user.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("teacher_profile", response.data)
        self.assertEqual(response.data["teacher_profile"]["school"], str(self.school))

    def test_update_user(self):
        """Should allow updating user details"""
        url = reverse("user-detail", args=[self.teacher.user.id])
        data = {
            "first_name": "Updated",
            "last_name": "Teacher",
            "email": self.teacher.user.email,  # Required for update
        }
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.user.refresh_from_db()
        self.assertEqual(self.teacher.user.first_name, "Updated")

    def test_deactivate_user(self):
        """Should allow deactivating users"""
        url = reverse("user-deactivate", args=[self.teacher.user.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.user.refresh_from_db()
        self.assertFalse(self.teacher.user.is_active)

    def test_activate_user(self):
        """Should allow reactivating users"""
        self.teacher.user.is_active = False
        self.teacher.user.save()
        url = reverse("user-activate", args=[self.teacher.user.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.user.refresh_from_db()
        self.assertTrue(self.teacher.user.is_active)

    def test_set_password(self):
        """Admin should be able to set user passwords"""
        url = reverse("user-set-password", args=[self.teacher.user.id])
        data = {"password": "newsecurepassword123"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh the user from database
        self.teacher.user.refresh_from_db()
        self.assertTrue(self.teacher.user.check_password("newsecurepassword123"))

    def test_me_endpoint(self):
        """Should return current user's profile"""
        self.client.force_authenticate(user=self.teacher.user)
        url = reverse("user-me")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.teacher.user.id)

    def test_search_users(self):
        """Should search users by name, email, or username"""
        search_url = reverse("user-search")
        response = self.client.get(search_url, {"q": self.teacher.user.last_name})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)
        # Check if teacher's ID is in the results
        self.assertIn(self.teacher.user.id, [user["id"] for user in response.data])

    def test_permissions_endpoint(self):
        """Should return user's effective permissions"""
        url = reverse("user-permissions", args=[self.teacher.user.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("user_type", response.data)
        self.assertEqual(response.data["user_type"], User.TEACHER)

    def test_teacher_cannot_list_users(self):
        """Teachers should only see their own profile"""
        self.client.force_authenticate(user=self.teacher.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only see themselves in the list
        user_ids = (
            [user["id"] for user in response.data["results"]]
            if "results" in response.data
            else [user["id"] for user in response.data]
        )
        self.assertEqual(len(user_ids), 1)
        self.assertEqual(user_ids[0], self.teacher.user.id)

    def test_parent_cannot_list_users(self):
        """Parents should only see their own profile"""
        self.client.force_authenticate(user=self.parent.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only see themselves in the list
        user_ids = (
            [user["id"] for user in response.data["results"]]
            if "results" in response.data
            else [user["id"] for user in response.data]
        )
        self.assertEqual(len(user_ids), 1)
        self.assertEqual(user_ids[0], self.parent.user.id)

    def test_cross_school_user_access(self):
        """Should not allow access to users from other schools"""
        other_school = SchoolFactory()
        other_teacher = TeacherFactory(school=other_school)

        url = reverse("user-detail", args=[other_teacher.user.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_sessions_relation(self):
        """Should include user sessions in detailed view"""
        # Create a session for the teacher
        session = Session.objects.create(
            session_key="test_session_123",
            session_data="{}",
            expire_date=timezone.now() + timezone.timedelta(days=1),
        )
        UserSessionFactory(user=self.teacher.user, session=session)

        url = reverse("user-detail", args=[self.teacher.user.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(
                s["session_key"] == "test_session_123"
                for s in response.data.get("sessions", [])
            )
        )


# python manage.py test skul_data.tests.users_tests.test_users_views
