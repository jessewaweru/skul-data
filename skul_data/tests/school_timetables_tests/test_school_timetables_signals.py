# tests/signals/test_timetable_signals.py
from django.test import TestCase
from skul_data.tests.school_timetables_tests.test_helpers import (
    create_test_timetable,
    create_test_lesson,
    create_test_school,
    create_test_class,
    create_test_subject,
    create_test_teacher,
    create_test_timeslot,
)
from skul_data.action_logs.models.action_log import ActionLog
from skul_data.action_logs.utils.action_log import set_test_mode
from skul_data.school_timetables.models.school_timetable import Lesson


class TimetableSignalsTest(TestCase):
    def setUp(self):
        set_test_mode(True)
        self.school, self.admin = create_test_school()
        self.school_class = create_test_class(self.school)

    def tearDown(self):
        set_test_mode(False)

    def test_timetable_pre_save_active(self):
        # Create an active timetable
        active_timetable = create_test_timetable(self.school_class, is_active=True)

        # Create another timetable and try to make it active
        new_timetable = create_test_timetable(
            self.school_class, academic_year="2023", term=2, is_active=True
        )

        # The signal should deactivate the first timetable
        active_timetable.refresh_from_db()
        self.assertFalse(active_timetable.is_active)
        self.assertTrue(new_timetable.is_active)

    def test_lesson_post_save_signal(self):
        # Create dependencies but not the lesson yet
        timetable = create_test_timetable(self.school_class)
        subject = create_test_subject(self.school)
        teacher = create_test_teacher(self.school)
        time_slot = create_test_timeslot(self.school)

        # Create lesson instance but don't save yet
        lesson = Lesson(
            timetable=timetable,
            subject=subject,
            teacher=teacher,
            time_slot=time_slot,
            is_double_period=False,
            room="Room 101",
            notes="Test lesson",
        )
        lesson._current_user = self.admin  # Set user before saving
        lesson.save()  # This will trigger the signal with created=True

        # Check if action log was created
        action_log = ActionLog.objects.filter(
            object_id=lesson.id,
            content_type__model="lesson",
        ).first()

        self.assertIsNotNone(action_log)
        self.assertEqual(action_log.action, "Created lesson")


# python manage.py test skul_data.tests.school_timetables_tests.test_school_timetables_signals
