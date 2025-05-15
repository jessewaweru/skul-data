from django.urls import reverse, resolve
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from skul_data.users.models.parent import Parent, ParentStatusChange, ParentNotification
from skul_data.tests.parents_tests.test_helpers import (
    create_test_school,
    create_test_parent,
    create_test_student,
    create_test_role,
)
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.school_admin import SchoolAdmin

User = get_user_model()


class ParentViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)
        self.student2 = create_test_student(self.school, first_name="Another")

        # Create a role with parent management permissions
        self.role = create_test_role(
            self.school,
            permissions=[
                "view_parents",
                "manage_parents",
                "assign_children",
                "change_parent_status",
            ],
        )

        # Create admin user
        self.admin_user = User.objects.create_user(
            email="adminuser@test.com",
            username="adminuser",
            password="testpass",
            user_type=User.SCHOOL_ADMIN,
        )
        SchoolAdmin.objects.create(
            user=self.admin_user,
            school=self.school,
            is_primary=False,
        )
        self.admin_user.role = self.role
        self.admin_user.save()

        # Create teacher user
        self.teacher_user = User.objects.create_user(
            email="teacher@test.com",
            username="teacher",
            password="testpass",
            user_type=User.TEACHER,
        )
        Teacher.objects.create(
            user=self.teacher_user,
            school=self.school,
        )

        # Create another parent
        self.other_parent_user = User.objects.create_user(
            email="otherparent@test.com",
            username="otherparent",
            password="testpass",
            user_type=User.PARENT,
        )
        self.other_parent = Parent.objects.create(
            user=self.other_parent_user,
            school=self.school,
            phone_number="+254733333333",
        )

        self.client.force_authenticate(user=self.admin_user)

    def test_parent_list_url_resolves(self):
        url = reverse("parent-list")
        self.assertEqual(resolve(url).func.cls.__name__, "ParentViewSet")

    def test_list_parents(self):
        url = reverse("parent-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # parent + other_parent

    def test_parent_detail_url_resolves(self):
        url = reverse("parent-detail", args=[self.parent.id])
        self.assertEqual(resolve(url).func.cls.__name__, "ParentViewSet")

    def test_retrieve_parent(self):
        url = reverse("parent-detail", args=[self.parent.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "parent@test.com")

    def test_create_parent_url_resolves(self):
        url = reverse("parent-list")
        self.assertEqual(resolve(url).func.cls.__name__, "ParentViewSet")

    def test_create_parent(self):
        url = reverse("parent-list")
        data = {
            "email": "newparent@test.com",
            "first_name": "New",
            "last_name": "Parent",
            "phone_number": "+254744444444",
            "school": self.school.id,
            "address": "123 New Street",
            "occupation": "New Occupation",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Parent.objects.count(), 3)
        # Fix: Get the email from user relation instead of direct access
        new_parent = Parent.objects.get(user__email="newparent@test.com")
        self.assertEqual(new_parent.user.email, "newparent@test.com")

    def test_update_parent(self):
        url = reverse("parent-detail", args=[self.parent.id])
        data = {
            "phone_number": "+254755555555",
            "address": "Updated Address",
            "occupation": "Updated Occupation",
        }
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.phone_number, "+254755555555")
        self.assertEqual(self.parent.address, "Updated Address")

    def test_change_status_url_resolves(self):
        url = reverse("parent-change-status", args=[self.parent.id])
        resolved = resolve(url)
        self.assertEqual(resolved.func.cls.__name__, "ParentViewSet")
        self.assertEqual(resolved.func.actions["post"], "change_status")

    def test_change_parent_status(self):
        url = reverse("parent-change-status", args=[self.parent.id])
        data = {"status": "ACTIVE", "reason": "Approved by admin"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.status, "ACTIVE")
        self.assertTrue(ParentStatusChange.objects.filter(parent=self.parent).exists())

    def test_assign_children_url_resolves(self):
        url = reverse("parent-assign-children", args=[self.parent.id])
        resolved = resolve(url)
        self.assertEqual(resolved.func.cls.__name__, "ParentViewSet")
        self.assertEqual(resolved.func.actions["post"], "assign_children")

    def test_assign_children(self):
        url = reverse("parent-assign-children", args=[self.parent.id])
        data = {"student_ids": [self.student.id, self.student2.id], "action": "ADD"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.parent.children.count(), 2)

    def test_parent_notifications_url_resolves(self):
        url = reverse("parent-notifications", args=[self.parent.id])
        resolved = resolve(url)
        self.assertEqual(resolved.func.cls.__name__, "ParentViewSet")
        # Fix: Check if "get" key exists in actions dictionary
        self.assertTrue("get" in resolved.func.actions)
        self.assertEqual(resolved.func.actions["get"], "notifications")

    def test_parent_notifications(self):
        # Create a notification first
        ParentNotification.objects.create(
            parent=self.parent,
            message="Test notification",
            notification_type="ACADEMIC",
        )

        url = reverse("parent-notifications", args=[self.parent.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["message"], "Test notification")

    def test_parent_permissions(self):
        # Test teacher can't manage parents
        self.client.force_authenticate(user=self.teacher_user)
        url = reverse("parent-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Create a role with view_parents permission for the parent user
        parent_role = create_test_role(
            self.school, name="Parent Role", permissions=["view_parents"]
        )
        self.parent.user.role = parent_role
        self.parent.user.save()

        # Test parent can see their own profile
        self.client.force_authenticate(user=self.parent.user)
        url = reverse("parent-detail", args=[self.parent.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Try to access another parent's profile
        url = reverse("parent-detail", args=[self.other_parent.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_parent_analytics_url_resolves(self):
        url = reverse("parent-analytics")
        resolved = resolve(url)
        self.assertEqual(resolved.func.cls.__name__, "ParentViewSet")
        # Fix: Check if "get" key exists in actions dictionary
        self.assertTrue("get" in resolved.func.actions)
        self.assertEqual(resolved.func.actions["get"], "analytics")

    def test_parent_analytics(self):
        url = reverse("parent-analytics")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_parents"], 2)
        self.assertEqual(len(response.data["parents_by_status"]), 1)


class ParentNotificationViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)

        # Create a notification
        self.notification = ParentNotification.objects.create(
            parent=self.parent,
            message="Test notification",
            notification_type="ACADEMIC",
        )

        # Create a school admin user - FIXED: Don't pass school directly
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            username="admin",
            password="testpass",
            user_type=User.SCHOOL_ADMIN,
        )

        # Create the relationship to school through SchoolAdmin model
        SchoolAdmin.objects.create(
            user=self.admin_user,
            school=self.school,
            is_primary=False,
        )

        self.client.force_authenticate(user=self.admin_user)

    def test_notification_list_url_resolves(self):
        url = reverse("parent-notification-list")
        self.assertEqual(resolve(url).func.cls.__name__, "ParentNotificationViewSet")

    def test_list_notifications(self):
        url = reverse("parent-notification-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_mark_as_read_url_resolves(self):
        url = reverse("parent-notification-mark-as-read", args=[self.notification.id])
        resolved = resolve(url)
        self.assertEqual(resolved.func.cls.__name__, "ParentNotificationViewSet")
        self.assertEqual(resolved.func.actions["post"], "mark_as_read")

    def test_mark_as_read(self):
        url = reverse("parent-notification-mark-as-read", args=[self.notification.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_all_as_read_url_resolves(self):
        url = reverse("parent-notification-mark-all-as-read")
        resolved = resolve(url)
        self.assertEqual(resolved.func.cls.__name__, "ParentNotificationViewSet")
        self.assertEqual(resolved.func.actions["post"], "mark_all_as_read")

    def test_mark_all_as_read(self):
        # Create another unread notification
        ParentNotification.objects.create(
            parent=self.parent,
            message="Another notification",
            notification_type="ATTENDANCE",
        )

        url = reverse("parent-notification-mark-all-as-read")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ParentNotification.objects.filter(is_read=False).count(), 0)

    def test_unread_count_url_resolves(self):
        url = reverse("parent-notification-unread-count")
        resolved = resolve(url)
        self.assertEqual(resolved.func.cls.__name__, "ParentNotificationViewSet")
        # Fix: Check if "get" key exists in actions dictionary
        self.assertTrue("get" in resolved.func.actions)
        self.assertEqual(resolved.func.actions["get"], "unread_count")

    def test_unread_count(self):
        url = reverse("parent-notification-unread-count")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 1)


class ParentStatusChangeViewSetTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)

        # Create a status change
        self.status_change = ParentStatusChange.objects.create(
            parent=self.parent,
            changed_by=self.admin,
            from_status="PENDING",
            to_status="ACTIVE",
            reason="Approved",
        )

        # Create a school admin user - FIXED: Don't pass school directly
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            username="admin",
            password="testpass",
            user_type=User.SCHOOL_ADMIN,
        )

        # Create the relationship to school through SchoolAdmin model
        SchoolAdmin.objects.create(
            user=self.admin_user,
            school=self.school,
            is_primary=False,
        )

        self.client.force_authenticate(user=self.admin_user)

    def test_status_change_list_url_resolves(self):
        url = reverse("parent-status-change-list")
        self.assertEqual(resolve(url).func.cls.__name__, "ParentStatusChangeViewSet")

    def test_list_status_changes(self):
        url = reverse("parent-status-change-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_recent_activity_url_resolves(self):
        url = reverse("parent-status-change-recent-activity")
        resolved = resolve(url)
        self.assertEqual(resolved.func.cls.__name__, "ParentStatusChangeViewSet")
        # Fix: Check if "get" key exists in actions dictionary
        self.assertTrue("get" in resolved.func.actions)
        self.assertEqual(resolved.func.actions["get"], "recent_activity")

    def test_recent_activity(self):
        url = reverse("parent-status-change-recent-activity")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


# python manage.py test skul_data.tests.parents_tests.test_parents_views
