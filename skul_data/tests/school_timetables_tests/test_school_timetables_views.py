from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework import status
from django.urls import reverse
from skul_data.tests.school_timetables_tests.test_helpers import (
    create_test_timeslot,
    create_test_timetable_structure,
    create_test_timetable,
    create_test_lesson,
    create_test_constraint,
    create_test_subject_group,
    create_test_teacher_availability,
    create_test_school,
    create_test_class,
    create_test_teacher,
    create_test_subject,
    create_test_user,
)
from skul_data.users.models.base_user import User
from skul_data.school_timetables.models.school_timetable import (
    Timetable,
    TimetableStructure,
)
from skul_data.school_timetables.models.school_timetable import TimeSlot
from datetime import time


class TimeSlotViewSetTest(TestCase):
    def setUp(self):
        TimeSlot.objects.all().delete()
        TimetableStructure.objects.all().delete()
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.factory = APIRequestFactory()
        self.timeslot = create_test_timeslot(self.school)

        # Create admin user with permissions
        self.admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.SCHOOL_ADMIN,
            school=self.school,
            role_permissions=["manage_timetable_settings"],
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_timeslots(self):
        url = reverse("school_timetables:time-slots-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # Check count
        self.assertEqual(len(response.data["results"]), 1)  # Check results

    def test_create_timeslot(self):
        url = reverse("school_timetables:time-slots-list")
        data = {
            "school": self.school.id,  # Add this line
            "name": "New Period",
            "start_time": "09:00:00",  # Changed from 08:00:00
            "end_time": "09:40:00",  # Changed from 08:40:00
            "day_of_week": "WED",  # Changed from TUE
            "is_break": False,
            "order": 2,
            "is_active": True,
        }
        response = self.client.post(url, data, format="json")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Period")

    def test_retrieve_timeslot(self):
        url = reverse("school_timetables:time-slots-detail", args=[self.timeslot.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.timeslot.id)

    def test_update_timeslot(self):
        url = reverse("school_timetables:time-slots-detail", args=[self.timeslot.id])
        data = {"name": "Updated Period"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Period")

    def test_delete_timeslot(self):
        url = reverse("school_timetables:time-slots-detail", args=[self.timeslot.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TimetableStructureViewSetTest(TestCase):
    def setUp(self):
        TimeSlot.objects.all().delete()
        TimetableStructure.objects.all().delete()
        Timetable.objects.all().delete()
        self.client = APIClient()
        self.school, self.admin = create_test_school()

        # Create timetable structure - this was missing
        self.structure = create_test_timetable_structure(self.school)

        # Create admin user with permissions
        self.admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.SCHOOL_ADMIN,
            school=self.school,
            role_permissions=["manage_timetable_settings"],
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_structures(self):
        url = reverse("school_timetables:timetable-structures-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)

    def test_generate_slots(self):
        url = reverse(
            "school_timetables:timetable-structures-generate-slots",
            args=[self.structure.id],  # Now this will work
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if slots were generated
        timeslots = TimeSlot.objects.filter(school=self.school)
        self.assertGreater(timeslots.count(), 0)
        self.assertGreater(timeslots.count(), 0)


class TimetableViewSetTest(TestCase):
    def setUp(self):
        TimeSlot.objects.all().delete()
        TimetableStructure.objects.all().delete()
        Timetable.objects.all().delete()
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.school_class = create_test_class(self.school)
        self.timetable = create_test_timetable(self.school_class)

        self.timetable_structure = create_test_timetable_structure(self.school)
        # Create admin user with permissions
        self.admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.SCHOOL_ADMIN,
            school=self.school,
            role_permissions=["manage_timetables"],
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_timetables(self):
        url = reverse("school_timetables:timetables-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # Check count
        self.assertEqual(len(response.data["results"]), 1)  # Check results

    def test_activate_timetable(self):
        url = reverse("school_timetables:timetables-activate", args=[self.timetable.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if timetable is now active
        self.timetable.refresh_from_db()
        self.assertTrue(self.timetable.is_active)

    def test_generate_timetables(self):
        url = reverse("school_timetables:timetables-generate")
        data = {
            "school_class_ids": [self.school_class.id],
            "academic_year": "2023",
            "term": 2,
            "regenerate_existing": False,
            "apply_constraints": True,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check if timetable was created
        timetables = Timetable.objects.filter(school_class=self.school_class)
        self.assertEqual(timetables.count(), 2)  # Original + new one

    def test_clone_timetables(self):
        # Create source with unique year/term
        source_timetable = self.timetable  # Use existing timetable
        url = reverse("school_timetables:timetables-clone")
        data = {
            "source_academic_year": source_timetable.academic_year,
            "source_term": source_timetable.term,
            "target_academic_year": "2024",  # Different year
            "target_term": 2,  # Different term
            "school_class_ids": [self.school_class.id],
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LessonViewSetTest(TestCase):
    def setUp(self):
        TimeSlot.objects.all().delete()
        TimetableStructure.objects.all().delete()
        Timetable.objects.all().delete()
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.school_class = create_test_class(self.school)
        self.timetable = create_test_timetable(self.school_class)
        self.teacher = create_test_teacher(self.school)
        self.subject = create_test_subject(self.school)
        self.timeslot = create_test_timeslot(self.school)
        self.lesson = create_test_lesson(
            self.timetable, self.subject, self.teacher, self.timeslot
        )

        # Create admin user with permissions
        self.admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.SCHOOL_ADMIN,
            school=self.school,
            role_permissions=["manage_timetables"],
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_lessons(self):
        url = reverse("school_timetables:lessons-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # Check count
        self.assertEqual(len(response.data["results"]), 1)  # Check results

    def test_create_lesson(self):
        url = reverse("school_timetables:lessons-list")
        # Create a unique timeslot by specifying different parameters
        new_timeslot = create_test_timeslot(
            self.school,
            name="Unique Period",
            start_time=time(9, 0),  # Different start time
            end_time=time(9, 40),  # Different end time
            day_of_week="WED",  # Explicit day
        )
        data = {
            "timetable": self.timetable.id,
            "subject": self.subject.id,
            "teacher": self.teacher.id,
            "time_slot": new_timeslot.id,
            "is_double_period": True,
            "room": "Lab 1",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_double_period"])


class TimetableConstraintViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.constraint = create_test_constraint(self.school)

        # Create admin user with permissions
        self.admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.SCHOOL_ADMIN,
            school=self.school,
            role_permissions=["manage_timetable_settings"],
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_constraints(self):
        url = reverse("school_timetables:timetable-constraints-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # Check count
        self.assertEqual(len(response.data["results"]), 1)  # Check results

    def test_create_constraint(self):
        url = reverse("school_timetables:timetable-constraints-list")
        data = {
            "school": self.school.id,
            "constraint_type": "SCIENCE_DOUBLE",
            "is_hard_constraint": True,
            "parameters": {"subject_id": 1},
            "description": "Science needs double period",
            "is_active": True,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["constraint_type"], "SCIENCE_DOUBLE")


class SubjectGroupViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.subject1 = create_test_subject(self.school, name="Math")
        self.subject2 = create_test_subject(self.school, name="Science")
        self.group = create_test_subject_group(
            self.school, subjects=[self.subject1, self.subject2]
        )

        # Create admin user with permissions
        self.admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.SCHOOL_ADMIN,
            school=self.school,
            role_permissions=["manage_timetable_settings"],
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_groups(self):
        url = reverse("school_timetables:subject-groups-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # Check count
        self.assertEqual(len(response.data["results"]), 1)  # Check results

    def test_create_group(self):
        url = reverse("school_timetables:subject-groups-list")
        data = {
            "school": self.school.id,
            "name": "Science Group",
            "subject_ids": [self.subject1.id, self.subject2.id],
            "description": "Group for science subjects",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["subjects"]), 2)


class TeacherAvailabilityViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.availability = create_test_teacher_availability(self.teacher)

        # Create admin user with permissions
        self.admin_user = create_test_user(
            email="admin@test.com",
            user_type=User.SCHOOL_ADMIN,
            school=self.school,
            role_permissions=["manage_timetable_settings"],
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_availabilities(self):
        url = reverse("school_timetables:teacher-availability-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # Check count
        self.assertEqual(len(response.data["results"]), 1)  # Check results

    def test_bulk_update(self):
        url = reverse("school_timetables:teacher-availability-bulk-update")
        data = {
            "updates": [
                {
                    "teacher_id": self.teacher.id,
                    "day_of_week": "MON",
                    "is_available": False,
                    "reason": "Weekly meeting",
                }
            ]
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], 1)


# python manage.py test skul_data.tests.school_timetables_tests.test_school_timetables_views
