from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.scheduler.models.scheduler import SchoolEvent, EventRSVP
from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from django.core.files.uploadedfile import SimpleUploadedFile


class SchoolEventModelTest(TestCase):
    def setUp(self):
        # Create test school admin USER (not SchoolAdmin profile yet)
        self.school_admin_user = User.objects.create_user(
            email="admin@school.com",
            password="testpass123",
            user_type=User.SCHOOL_ADMIN,
            first_name="Admin",
            last_name="User",
        )

        # Create School and SchoolAdmin profile
        self.school = School.objects.create(
            name="Test School",
            email="test@school.com",
            schooladmin=self.school_admin_user,  # Assuming School.schooladmin is a FK to User
        )
        # If you have a separate SchoolAdmin profile model:
        self.school_admin = SchoolAdmin.objects.create(
            user=self.school_admin_user, school=self.school, is_primary=True
        )

        # Create test teacher USER
        self.teacher_user = User.objects.create_user(
            email="teacher@school.com",
            password="testpass123",
            user_type=User.TEACHER,
            first_name="Teacher",
            last_name="User",  # REMOVE school=self.school from here
        )
        # Create Teacher profile
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, school=self.school  # School is set here instead
        )

        # Similarly for parent
        self.parent_user = User.objects.create_user(
            email="parent@school.com",
            password="testpass123",
            user_type=User.PARENT,
            first_name="Parent",
            last_name="User",
        )
        self.parent = Parent.objects.create(user=self.parent_user, school=self.school)

        # Create test class
        self.school_class = SchoolClass.objects.create(
            name="Class 1",
            school=self.school,
            grade_level="Grade 3",
            level="PRIMARY",
        )

        self.event = SchoolEvent.objects.create(
            title="Test Event",
            description="Test Description",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=2),
            event_type="meeting",
            target_type="all",
            created_by=self.school_admin_user,  # Pass the User, not SchoolAdmin
            school=self.school,
        )

    def test_event_creation(self):
        self.assertEqual(self.event.title, "Test Event")
        self.assertEqual(self.event.event_type, "meeting")
        self.assertEqual(self.event.target_type, "all")
        self.assertEqual(
            self.event.created_by, self.school_admin.user
        )  # Fixed comparison
        self.assertEqual(self.event.school, self.school)

    def test_event_str_method(self):
        expected_str = f"Test Event ({self.event.start_datetime.strftime('%Y-%m-%d')})"
        self.assertEqual(str(self.event), expected_str)

    def test_event_clean_method_valid(self):
        # Should not raise any exception
        self.event.clean()

    def test_event_clean_method_invalid_dates(self):
        self.event.end_datetime = self.event.start_datetime - timedelta(hours=1)
        with self.assertRaises(ValidationError):
            self.event.clean()

    def test_event_clean_method_invalid_rsvp(self):
        self.event.requires_rsvp = True
        self.event.rsvp_deadline = self.event.start_datetime + timedelta(hours=1)
        with self.assertRaises(ValidationError):
            self.event.clean()

    def test_get_target_users_all(self):
        users = self.event.get_target_users()
        self.assertIn(self.teacher_user, users)
        self.assertIn(self.parent_user, users)

    def test_get_target_users_teachers(self):
        self.event.target_type = "teachers"
        users = self.event.get_target_users()
        self.assertIn(self.teacher_user, users)
        self.assertNotIn(self.parent_user, users)

    def test_get_target_users_parents(self):
        self.event.target_type = "parents"
        users = self.event.get_target_users()
        self.assertNotIn(self.teacher_user, users)
        self.assertIn(self.parent_user, users)

    def test_get_target_users_specific(self):
        self.event.target_type = "specific"
        self.event.targeted_teachers.add(self.teacher)
        users = self.event.get_target_users()
        self.assertIn(self.teacher_user, users)
        self.assertNotIn(self.parent_user, users)

    def test_get_target_users_classes(self):
        self.event.target_type = "classes"
        self.event.targeted_classes.add(self.school_class)
        # Need to assign teacher to class and parent to student in class
        # For brevity, we'll just test the structure
        users = self.event.get_target_users()
        self.assertEqual(users.count(), 0)  # No assignments yet


class EventRSVPModelTest(TestCase):
    def setUp(self):
        self.school_admin = User.objects.create_user(
            email="admin@school.com",
            password="testpass123",
            user_type=User.SCHOOL_ADMIN,
            first_name="Admin",
            last_name="User",
        )
        self.school = School.objects.create(
            name="Test School", email="test@school.com", schooladmin=self.school_admin
        )

        self.event = SchoolEvent.objects.create(
            title="Test Event",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=2),
            created_by=self.school_admin,
            school=self.school,
            requires_rsvp=True,
        )

        self.rsvp = EventRSVP.objects.create(
            event=self.event, user=self.school_admin, status="going"
        )

    def test_rsvp_creation(self):
        self.assertEqual(self.rsvp.event, self.event)
        self.assertEqual(self.rsvp.user, self.school_admin)
        self.assertEqual(self.rsvp.status, "going")

    def test_rsvp_str_method(self):
        expected_str = f"{self.school_admin} - {self.event}: going"
        self.assertEqual(str(self.rsvp), expected_str)

    def test_rsvp_unique_together(self):
        with self.assertRaises(Exception):  # IntegrityError
            EventRSVP.objects.create(
                event=self.event, user=self.school_admin, status="maybe"
            )


class SchoolEventLoggingTests(TestCase):
    def setUp(self):
        # Create test data (similar to your existing setup)
        self.school_admin_user = User.objects.create_user(
            email="admin@school.com",
            password="testpass123",
            user_type=User.SCHOOL_ADMIN,
            first_name="Admin",
            last_name="User",
        )
        self.school = School.objects.create(
            name="Test School",
            email="test@school.com",
            schooladmin=self.school_admin_user,
        )
        self.school_admin = SchoolAdmin.objects.create(
            user=self.school_admin_user, school=self.school, is_primary=True
        )

        self.teacher_user = User.objects.create_user(
            email="teacher@school.com",
            password="testpass123",
            user_type=User.TEACHER,
            first_name="Teacher",
            last_name="User",
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, school=self.school
        )

        self.parent_user = User.objects.create_user(
            email="parent@school.com",
            password="testpass123",
            user_type=User.PARENT,
            first_name="Parent",
            last_name="User",
        )
        self.parent = Parent.objects.create(user=self.parent_user, school=self.school)

        self.school_class = SchoolClass.objects.create(
            name="Class 1",
            school=self.school,
            grade_level="Grade 3",
            level="PRIMARY",
        )

        # Create a test file for attachments
        self.test_file = SimpleUploadedFile(
            "test_file.txt", b"file_content", content_type="text/plain"
        )

    def test_m2m_relationship_logging(self):
        """Test that M2M relationship changes are logged properly"""
        event = SchoolEvent.objects.create(
            title="Test Event",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=2),
            created_by=self.school_admin_user,
            school=self.school,
        )

        # Set teachers using our custom method
        event.targeted_teachers_set([self.teacher], user=self.school_admin_user)

        # Verify the log was created
        log = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(event),
            object_id=event.id,
            category=ActionCategory.UPDATE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(
            log.action, f"Updated teachers for related objects for event {event.id}"
        )  # Use event.id
        self.assertEqual(log.user, self.school_admin_user)
        self.assertEqual(log.metadata["targeted_teachers"], [self.teacher.id])

    def test_attachment_upload_logging(self):
        """Test that attachment uploads are logged properly"""
        event = SchoolEvent.objects.create(
            title="Test Event",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=2),
            created_by=self.school_admin_user,
            school=self.school,
        )

        # Simulate attachment upload
        event.attachment = self.test_file
        event.save(user=self.school_admin_user)

        # Verify the log was created
        log = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(event),
            object_id=event.id,
            category=ActionCategory.UPLOAD,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.action, f"Uploaded attachment to event {event.id}")
        self.assertEqual(log.user, self.school_admin_user)
        # Check that filename starts with expected path
        self.assertTrue(
            log.metadata["filename"].startswith("event_attachments/test_file")
        )
        # Check that it has .txt extension
        self.assertTrue(log.metadata["filename"].endswith(".txt"))


# python manage.py test skul_data.tests.scheduler_tests.test_scheduler_models
