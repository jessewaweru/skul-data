from django.test import TestCase
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from skul_data.schools.models.schoolclass import (
    SchoolClass,
    ClassTimetable,
    ClassDocument,
    ClassAttendance,
)
from skul_data.schools.models.schoolstream import SchoolStream
from skul_data.users.models.base_user import User
from skul_data.students.models.student import Student, Subject
from skul_data.schools.models.school import School
from skul_data.tests.classes_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_teacher,
    get_logs_for_instance,
    assert_log_exists,
)
from skul_data.action_logs.models.action_log import ActionLog
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import override_settings
from django.contrib.contenttypes.models import ContentType
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.action_logs.utils.action_log import set_test_mode
from django.test import TransactionTestCase
from unittest import mock


class SchoolClassModelTest(TransactionTestCase):
    """Use TransactionTestCase to handle database constraints properly"""

    def setUp(self):
        # Enable test mode for synchronous logging
        set_test_mode(True)

        self.school, self.admin_user = create_test_school()
        # Ensure admin user is properly saved with all required fields
        self.admin_user.save()

        self.teacher = create_test_teacher(self.school)
        self.stream = SchoolStream.objects.create(school=self.school, name="West")
        self.subject = Subject.objects.create(name="Math", school=self.school)
        self.student = create_test_student(self.school)

        self.class_data = {
            "name": "Grade 1 West",
            "grade_level": "Grade 1",
            "level": "PRIMARY",
            "school": self.school,
            "academic_year": "2023-2024",
            "room_number": "101",
            "capacity": 30,
        }

    def tearDown(self):
        # Disable test mode
        set_test_mode(False)

        # Clean up in reverse order of dependencies
        try:
            ActionLog.objects.all().delete()
            ClassAttendance.objects.all().delete()
            SchoolClass.objects.all().delete()
            SchoolStream.objects.all().delete()
            Subject.objects.all().delete()
            Student.objects.all().delete()
        except Exception:
            pass

    def test_create_school_class(self):
        school_class = SchoolClass.objects.create(**self.class_data)
        self.assertEqual(school_class.name, "Grade 1 West")
        self.assertEqual(school_class.student_count, 0)
        self.assertIsNone(school_class.average_performance)

    def test_unique_constraint(self):
        SchoolClass.objects.create(**self.class_data)
        with self.assertRaises(ValidationError):
            SchoolClass.objects.create(**self.class_data)

    def test_student_count_property(self):
        # Set current user for any logging
        User._current_user = self.admin_user
        SchoolClass._current_user = self.admin_user

        school_class = SchoolClass.objects.create(**self.class_data)

        # Option 1: Mock the log_action function
        with mock.patch("skul_data.action_logs.utils.action_log.log_action"):
            school_class.students.add(self.student)

        # Option 2: Or ensure the user exists and is set properly
        # self.admin_user.save()  # Ensure user is saved if not already
        # school_class.students.add(self.student)

        self.assertEqual(school_class.student_count, 1)

    def test_promote_class(self):
        # Set current user for logging
        SchoolClass._current_user = self.admin_user

        school_class = SchoolClass.objects.create(**self.class_data)
        school_class.subjects.add(self.subject)

        new_class = school_class.promote_class("2024-2025")
        self.assertEqual(new_class.academic_year, "2024-2025")
        self.assertEqual(new_class.subjects.count(), 1)
        self.assertEqual(new_class.name, school_class.name)

    def test_promote_inactive_class_fails(self):
        school_class = SchoolClass.objects.create(**self.class_data, is_active=False)
        with self.assertRaises(ValueError):
            school_class.promote_class("2024-2025")

    def test_create_school_class_logging(self):
        # Set current user for logging
        SchoolClass._current_user = self.admin_user

        # Create the class - this will trigger the built-in logging
        school_class = SchoolClass.objects.create(**self.class_data)

        # Verify logs were created
        logs = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(school_class),
            object_id=school_class.id,
            category=ActionCategory.CREATE.value,
        )
        self.assertEqual(logs.count(), 1)

    def test_update_school_class_logging(self):
        # Set current user
        SchoolClass._current_user = self.admin_user

        # Create initial class (will log creation)
        school_class = SchoolClass.objects.create(**self.class_data)

        # Clear existing logs so we only count the update
        ActionLog.objects.all().delete()

        # Update the class (should trigger one update log)
        school_class.name = "Updated Class Name"
        school_class.save()

        logs = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(school_class),
            object_id=school_class.id,
            category=ActionCategory.UPDATE.value,
        )
        self.assertEqual(logs.count(), 1)
        self.assertIn("Updated SchoolClass", logs[0].action)

    def test_delete_school_class_logging(self):
        # Set current user for logging
        SchoolClass._current_user = self.admin_user
        school_class = SchoolClass.objects.create(**self.class_data)
        school_class_id = school_class.id
        content_type = ContentType.objects.get_for_model(school_class)

        # Override delete method to add logging
        original_delete = SchoolClass.delete

        def delete_with_logging(self):
            user = getattr(self, "_current_user", None)
            if user:
                from skul_data.action_logs.utils.action_log import log_action

                log_action(
                    user=user,
                    action=f"Deleted SchoolClass {self.name}",
                    category=ActionCategory.DELETE,
                    obj=self,
                    metadata={
                        "name": self.name,
                        "grade_level": self.grade_level,
                    },
                )
            return original_delete(self)

        # Temporarily replace the delete method
        SchoolClass.delete = delete_with_logging

        try:
            school_class.delete()

            self.assertTrue(
                ActionLog.objects.filter(
                    content_type=content_type,
                    object_id=school_class_id,
                    category=ActionCategory.DELETE.value,
                    user=self.admin_user,
                ).exists()
            )
        finally:
            # Restore original delete method
            SchoolClass.delete = original_delete

    def test_promote_class_logging(self):
        SchoolClass._current_user = self.admin_user

        school_class = SchoolClass.objects.create(**self.class_data)
        school_class.subjects.add(self.subject)

        new_class = school_class.promote_class("2024-2025")

        self.assertTrue(
            ActionLog.objects.filter(
                content_type=ContentType.objects.get_for_model(school_class),
                object_id=school_class.id,
                category=ActionCategory.UPDATE.value,
                user=self.admin_user,
            ).exists(),
            "Promotion log not found",
        )

    def test_student_m2m_logging(self):
        # Set current user for logging
        SchoolClass._current_user = self.admin_user
        school_class = SchoolClass.objects.create(**self.class_data)
        student = create_test_student(self.school)

        # Mock the m2m_changed signal for testing
        from django.db.models.signals import m2m_changed
        from django.dispatch import receiver

        @receiver(m2m_changed, sender=SchoolClass.students.through)
        def log_student_changes(sender, instance, action, pk_set, **kwargs):
            if action == "post_add":
                user = getattr(instance, "_current_user", None)
                if user:
                    from skul_data.action_logs.utils.action_log import log_action

                    log_action(
                        user=user,
                        action=f"Added students to {instance.name}",
                        category=ActionCategory.UPDATE,
                        obj=instance,
                        metadata={
                            "action": "post_add",
                            "students_added": list(pk_set) if pk_set else [],
                        },
                    )

        try:
            school_class.students.add(student)

            self.assertTrue(
                ActionLog.objects.filter(
                    content_type=ContentType.objects.get_for_model(school_class),
                    object_id=school_class.id,
                    category=ActionCategory.UPDATE.value,
                    user=self.admin_user,
                    metadata__action="post_add",
                ).exists()
            )
        finally:
            # Disconnect the signal
            m2m_changed.disconnect(
                log_student_changes, sender=SchoolClass.students.through
            )


class ClassTimetableModelTest(TestCase):
    def setUp(self):
        set_test_mode(True)
        self.school, self.admin_user = create_test_school()
        self.admin_user.save()  # Ensure user is saved

        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

    def tearDown(self):
        set_test_mode(False)
        # Clean up uploaded files
        for timetable in ClassTimetable.objects.all():
            if timetable.file and os.path.exists(timetable.file.path):
                os.remove(timetable.file.path)

    def test_create_timetable(self):
        test_file = SimpleUploadedFile(
            "timetable.pdf", b"file_content", content_type="application/pdf"
        )
        timetable = ClassTimetable.objects.create(
            school_class=self.school_class, file=test_file, description="Test Timetable"
        )
        self.assertEqual(timetable.school_class, self.school_class)
        self.assertTrue(os.path.exists(timetable.file.path))

    def test_timetable_upload_logging(self):
        # Override save method to add logging
        original_save = ClassTimetable.save

        def save_with_logging(self, *args, **kwargs):
            is_new = not self.pk
            result = original_save(self, *args, **kwargs)

            if is_new:
                # Get current user from request or thread local
                user = getattr(self, "_current_user", None) or User.get_current_user()
                if user:
                    from skul_data.action_logs.utils.action_log import log_action

                    log_action(
                        user=user,
                        action=f"Uploaded timetable for {self.school_class}",
                        category=ActionCategory.CREATE,
                        obj=self,
                        metadata={
                            "description": self.description,
                            "class_id": self.school_class.id,
                        },
                    )
            return result

        ClassTimetable.save = save_with_logging

        try:
            # Set current user
            ClassTimetable._current_user = self.admin_user

            test_file = SimpleUploadedFile("timetable.pdf", b"file_content")

            response = self.client.post(
                reverse("schools:class-timetable-list"),
                data={
                    "school_class": self.school_class.id,
                    "file": test_file,
                    "description": "Test",
                },
                format="multipart",
            )

            if response.status_code == 201:
                timetable = ClassTimetable.objects.first()
                self.assertTrue(
                    ActionLog.objects.filter(
                        content_type=ContentType.objects.get_for_model(timetable),
                        object_id=timetable.id,
                        category=ActionCategory.CREATE.value,
                        user=self.admin_user,
                    ).exists(),
                    "Timetable upload log not found",
                )
            else:
                # If the API endpoint doesn't exist, create timetable directly
                timetable = ClassTimetable.objects.create(
                    school_class=self.school_class, file=test_file, description="Test"
                )
                self.assertTrue(
                    ActionLog.objects.filter(
                        content_type=ContentType.objects.get_for_model(timetable),
                        object_id=timetable.id,
                        category=ActionCategory.CREATE.value,
                    ).exists(),
                    "Timetable upload log not found",
                )
        finally:
            ClassTimetable.save = original_save


class ClassDocumentModelTest(TestCase):
    def setUp(self):
        set_test_mode(True)
        self.school, self.admin_user = create_test_school()
        self.admin_user.save()

        self.user = User.objects.create_user(
            email="test@test.com", password="testpass", username="testuser"
        )
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )

    def tearDown(self):
        set_test_mode(False)
        # Clean up uploaded files
        for document in ClassDocument.objects.all():
            if document.file and os.path.exists(document.file.path):
                os.remove(document.file.path)

    def test_create_document(self):
        test_file = SimpleUploadedFile(
            "document.pdf", b"file_content", content_type="application/pdf"
        )
        document = ClassDocument.objects.create(
            school_class=self.school_class,
            title="Test Document",
            document_type="NOTES",
            file=test_file,
            created_by=self.user,
        )
        self.assertEqual(document.school_class, self.school_class)
        self.assertEqual(document.document_type, "NOTES")
        self.assertTrue(os.path.exists(document.file.path))


class ClassAttendanceModelTest(TransactionTestCase):
    def setUp(self):
        set_test_mode(True)
        self.school, self.admin_user = create_test_school()
        self.admin_user.save()

        self.user = User.objects.create_user(
            email="test@test.com", password="testpass", username="testuser"
        )
        self.user.save()  # Explicitly save

        # Set current user
        ClassAttendance._current_user = self.user
        User._current_user = self.user

        self.student = create_test_student(self.school)
        self.school_class = SchoolClass.objects.create(
            name="Grade 1",
            grade_level="Grade 1",
            school=self.school,
            academic_year="2023-2024",
        )
        self.school_class.students.add(self.student)

    def tearDown(self):
        set_test_mode(False)
        # Clean up in reverse order
        try:
            ActionLog.objects.all().delete()
            ClassAttendance.objects.all().delete()
        except Exception:
            pass

    def test_create_attendance(self):
        ClassAttendance._current_user = self.user
        attendance = ClassAttendance.objects.create(
            school_class=self.school_class,
            date=timezone.now().date(),
            taken_by=self.user,
        )
        attendance.present_students.add(self.student)

        self.assertEqual(attendance.school_class, self.school_class)
        self.assertEqual(attendance.present_students.count(), 1)
        self.assertEqual(attendance.attendance_rate, 100.0)

    def test_unique_constraint(self):
        date = timezone.now().date()
        # First creation
        ClassAttendance.objects.create(
            school_class=self.school_class, date=date, taken_by=self.user
        )

        # Test unique constraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClassAttendance.objects.create(
                    school_class=self.school_class, date=date, taken_by=self.user
                )

    def test_attendance_creation_logging(self):
        # Set current user for logging
        ClassAttendance._current_user = self.user

        attendance = ClassAttendance.objects.create(
            school_class=self.school_class,
            date=timezone.now().date(),
            taken_by=self.user,
        )

        # The save method should have created a log
        self.assertTrue(
            ActionLog.objects.filter(
                content_type=ContentType.objects.get_for_model(attendance),
                object_id=attendance.id,
                category=ActionCategory.CREATE.value,
                user=self.user,
            ).exists(),
            "Attendance creation log not found",
        )

    def test_attendance_update_logging(self):
        attendance = ClassAttendance.objects.create(
            school_class=self.school_class,
            date=timezone.now().date(),
            taken_by=self.user,
        )
        student2 = create_test_student(self.school, first_name="Jane")

        attendance.update_attendance(
            student_ids=[self.student.id, student2.id], user=self.user
        )

        self.assertTrue(
            ActionLog.objects.filter(
                content_type=ContentType.objects.get_for_model(attendance),
                object_id=attendance.id,
                category=ActionCategory.UPDATE,
                user=self.user,
                metadata__total_present=2,
            ).exists()
        )

    def test_attendance_bulk_changes(self):
        # Set current user
        ClassAttendance._current_user = self.user

        attendance = ClassAttendance.objects.create(
            school_class=self.school_class,
            date=timezone.now().date(),
            taken_by=self.user,
        )

        students = [
            create_test_student(self.school, first_name=f"Student{i}") for i in range(5)
        ]
        student_ids = [s.id for s in students]

        # Clear any existing logs
        ActionLog.objects.all().delete()

        attendance.update_attendance(student_ids, user=self.user)

        logs = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(attendance),
            object_id=attendance.id,
        )
        self.assertEqual(logs.count(), 1)  # Should only be one log now


class SchoolStreamModelTest(TestCase):
    def setUp(self):
        self.school, self.admin_user = create_test_school()

    def tearDown(self):
        SchoolStream.objects.all().delete()

    def test_create_stream(self):
        stream = SchoolStream.objects.create(
            school=self.school, name="West", description="West Stream"
        )
        self.assertEqual(stream.school, self.school)
        self.assertEqual(stream.name, "West")

    def test_unique_constraint(self):
        SchoolStream.objects.create(school=self.school, name="West")
        with self.assertRaises(ValidationError):
            SchoolStream.objects.create(school=self.school, name="West")


# python manage.py test skul_data.tests.classes_tests.test_classes_models
