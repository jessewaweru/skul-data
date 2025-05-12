from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from skul_data.users.models import User
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.scheduler.models.scheduler import SchoolEvent, EventRSVP


class SchoolEventViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create school admin
        self.admin = User.objects.create_user(
            email="admin@school.com",
            password="adminpass",
            user_type=User.SCHOOL_ADMIN,
            first_name="Admin",
            last_name="User",
        )

        # Create the school with the admin
        self.school = School.objects.create(
            name="Test School", email="test@school.com", schooladmin=self.admin
        )

        # Create the SchoolAdmin profile for the admin user
        self.admin_profile = SchoolAdmin.objects.create(
            user=self.admin, school=self.school, is_primary=True
        )

        # Create teacher
        self.teacher_user = User.objects.create_user(
            email="teacher@school.com",
            password="teacherpass",
            user_type=User.TEACHER,
            first_name="Teacher",
            last_name="User",
        )

        # Create the teacher profile with the correct school
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            school=self.school,
        )

        # Create parent
        self.parent_user = User.objects.create_user(
            email="parent@school.com",
            password="parentpass",
            user_type=User.PARENT,
            first_name="Parent",
            last_name="User",
        )

        # Create the parent profile with the correct school
        self.parent = Parent.objects.create(
            user=self.parent_user,
            school=self.school,
        )

        # Create class
        self.school_class = SchoolClass.objects.create(
            name="Class 1", school=self.school
        )

        # Create events
        self.event1 = SchoolEvent.objects.create(
            title="Admin Event",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=2),
            created_by=self.admin,
            school=self.school,
            target_type="all",
        )

        # Create event2
        self.event2 = SchoolEvent.objects.create(
            title="Teacher Event",
            start_datetime=timezone.now() + timedelta(days=2),
            end_datetime=timezone.now() + timedelta(days=2, hours=1),
            created_by=self.admin,
            school=self.school,
            target_type="teachers",
        )

        # Set the many-to-many relationship after creating the object
        self.event2.targeted_teachers.add(self.teacher)

    def test_list_events_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse("scheduler:event-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_events_as_teacher(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get(reverse("scheduler:event-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Teacher should see both events (all and teachers)
        self.assertEqual(len(response.data), 2)

    def test_list_events_as_parent(self):
        self.client.force_authenticate(user=self.parent_user)
        response = self.client.get(reverse("scheduler:event-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Parent should only see the "all" event
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Admin Event")

    # def test_create_event_as_admin(self):
    #     self.client.force_authenticate(user=self.admin)
    #     data = {
    #         "title": "New Event",
    #         "start_datetime": (timezone.now() + timedelta(days=3)).isoformat(),
    #         "end_datetime": (timezone.now() + timedelta(days=3, hours=1)).isoformat(),
    #         "event_type": "meeting",
    #         "target_type": "parents",
    #         "targeted_parents": [self.parent.id],
    #     }
    #     response = self.client.post(
    #         reverse("scheduler:event-list"), data=data, format="json"
    #     )
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #     self.assertEqual(SchoolEvent.objects.count(), 3)

    def test_create_event_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        now = timezone.now()
        data = {
            "title": "New Event",
            "start_datetime": (now + timedelta(days=3)).isoformat(),
            "end_datetime": (now + timedelta(days=3, hours=1)).isoformat(),
            "event_type": "meeting",
            "target_type": "parents",
            "targeted_parents": [self.parent.id],
        }
        response = self.client.post(
            reverse("scheduler:event-list"), data=data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SchoolEvent.objects.count(), 3)

    def test_create_event_invalid_dates(self):
        self.client.force_authenticate(user=self.admin)
        data = {
            "title": "Invalid Event",
            "start_datetime": (timezone.now() + timedelta(days=4)).isoformat(),
            "end_datetime": (timezone.now() + timedelta(days=3)).isoformat(),
            "event_type": "general",
        }
        response = self.client.post(
            reverse("scheduler:event-list"), data=data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_event(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(
            reverse("scheduler:event-detail", kwargs={"pk": self.event1.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Admin Event")

    def test_update_event(self):
        self.client.force_authenticate(user=self.admin)
        data = {
            "title": "Updated Event",
            "start_datetime": self.event1.start_datetime.isoformat(),
            "end_datetime": self.event1.end_datetime.isoformat(),
            "event_type": "announcement",
        }
        response = self.client.patch(
            reverse("scheduler:event-detail", kwargs={"pk": self.event1.id}),
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.event1.refresh_from_db()
        self.assertEqual(self.event1.title, "Updated Event")

    def test_delete_event(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(
            reverse("scheduler:event-detail", kwargs={"pk": self.event1.id})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(SchoolEvent.objects.count(), 1)

    def test_user_event_list(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get(reverse("scheduler:user-event-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) <= 10)  # Limited to 10 events

    def test_create_rsvp(self):
        self.event1.requires_rsvp = True
        self.event1.save()

        self.client.force_authenticate(user=self.teacher_user)
        data = {"status": "going"}
        response = self.client.post(
            reverse("scheduler:event-rsvp", kwargs={"event_id": self.event1.id}),
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            EventRSVP.objects.filter(event=self.event1, user=self.teacher_user).exists()
        )

    def test_export_calendar(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse("scheduler:export-calendar"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/calendar")
        self.assertIn(b"BEGIN:VCALENDAR", response.content)


# python manage.py test skul_data.tests.scheduler_tests.test_scheduler_views
