from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from datetime import timedelta
from celery import current_app
from django.db import transaction
from skul_data.tests.analytics_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_student,
    create_test_class,
    create_test_subject,
    create_test_academic_record,
    create_test_teacher_attendance,
    create_test_class_attendance,
)
from skul_data.analytics.models.analytics import CachedAnalytics, AnalyticsAlert
from skul_data.analytics.utils.tasks import (
    cache_daily_analytics,
    check_and_generate_alerts,
)
from skul_data.users.models.teacher import TeacherAttendance
from skul_data.schools.models.schoolclass import ClassAttendance
from skul_data.analytics.models.analytics import AnalyticsAlert
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.students.models.student import Subject
from django.db.models import Count, Value
from django.db.models.functions import Concat
from django.db.models.signals import post_save
from skul_data.analytics.signals.analytics import (
    check_low_performance,
    check_consistently_low_performance,
    check_teacher_attendance,
    check_frequent_absences,
    check_low_class_attendance,
)


class AnalyticsTasksTest(TransactionTestCase):
    def setUp(self):
        super().setUp()
        # Disconnect signals that create alerts during task tests
        post_save.disconnect(check_low_performance, sender=AcademicRecord)
        post_save.disconnect(check_consistently_low_performance, sender=AcademicRecord)
        post_save.disconnect(check_teacher_attendance, sender=TeacherAttendance)
        post_save.disconnect(check_frequent_absences, sender=TeacherAttendance)
        # Check if signal is connected before disconnecting
        if post_save.has_listeners(ClassAttendance):
            print("DEBUG: Disconnecting check_low_class_attendance signal")
            post_save.disconnect(check_low_class_attendance, sender=ClassAttendance)
        else:
            print("DEBUG: Signal already disconnected")

        current_app.conf.task_always_eager = True
        current_app.conf.task_eager_propogates = True
        # Create test data once
        with transaction.atomic():
            self.school, self.admin = create_test_school()
            self.teacher = create_test_teacher(self.school)
            self.student = create_test_student(self.school, teacher=self.teacher)
            self.school_class = create_test_class(self.school)
            self.subject = create_test_subject(self.school)

        # Clear all possible alert data before each test
        with transaction.atomic():
            AnalyticsAlert.objects.all().delete()
            AcademicRecord.objects.all().delete()
            TeacherAttendance.objects.all().delete()
            ClassAttendance.objects.all().delete()

    def tearDown(self):
        # Reconnect signals after tests
        post_save.connect(check_low_performance, sender=AcademicRecord)
        post_save.connect(check_consistently_low_performance, sender=AcademicRecord)
        post_save.connect(check_teacher_attendance, sender=TeacherAttendance)
        post_save.connect(check_frequent_absences, sender=TeacherAttendance)
        post_save.connect(check_low_class_attendance, sender=ClassAttendance)
        super().tearDown()
        # Clean up all test data
        with transaction.atomic():
            TeacherAttendance.objects.all().delete()
            AnalyticsAlert.objects.all().delete()
            AcademicRecord.objects.all().delete()
            ClassAttendance.objects.all().delete()
            Subject.objects.filter(school=self.school).exclude(
                pk=self.subject.pk
            ).delete()
        super().tearDown()

    def test_cache_daily_analytics(self):
        # Run the task
        result = cache_daily_analytics.delay()
        self.assertTrue(result.successful())

        # Check for existence rather than exact count
        self.assertTrue(
            CachedAnalytics.objects.filter(analytics_type="overview").exists()
        )
        self.assertTrue(
            CachedAnalytics.objects.filter(analytics_type="teachers").exists()
        )
        self.assertTrue(
            CachedAnalytics.objects.filter(analytics_type="students").exists()
        )
        self.assertTrue(
            CachedAnalytics.objects.filter(analytics_type="classes").exists()
        )

    def test_check_and_generate_alerts(self):
        print("\n=== Starting test_check_and_generate_alerts ===")

        # Test 1: Verify initial state with no data produces no alerts
        print("\n--- Test 1: Initial state check ---")
        with transaction.atomic():
            AcademicRecord.objects.all().delete()
            AnalyticsAlert.objects.all().delete()
            print("DEBUG: Deleted all academic records and alerts")

        result = check_and_generate_alerts.delay()
        self.assertTrue(result.successful())
        print(f"DEBUG: Initial alerts count: {AnalyticsAlert.objects.count()}")
        self.assertEqual(
            AnalyticsAlert.objects.count(), 0, "Initial run should produce no alerts"
        )

        # Test 2: Single failing academic record (should not trigger alert)
        print("\n--- Test 2: Single failing record ---")
        with transaction.atomic():
            AcademicRecord.objects.all().delete()
            AnalyticsAlert.objects.all().delete()
            print("DEBUG: Cleared all academic records and alerts")

            # Create exactly one failing record
            record = create_test_academic_record(
                self.student,
                self.subject,
                self.teacher,
                score=35,  # Failing score
                term="Term1",
                school_year="2023",
            )
            print(
                f"DEBUG: Created 1 failing record: {record.id} with score {record.score}"
            )

        # Debug: Verify records in DB
        records = AcademicRecord.objects.all()
        print(f"DEBUG: Records in DB: {records.count()}")
        for r in records:
            print(
                f"  - ID: {r.id}, Student: {r.student.id}, Subject: {r.subject.id}, Score: {r.score}"
            )

        result = check_and_generate_alerts.delay()
        self.assertTrue(result.successful())

        # Debug: Check what alerts were created
        alerts = AnalyticsAlert.objects.all()
        print(f"DEBUG: Alerts after single failing record: {alerts.count()}")
        for alert in alerts:
            print(
                f"  - Type: {alert.alert_type}, Title: {alert.title}, Related: {alert.related_model}"
            )

        # Verify no performance alert was created
        performance_alerts = AnalyticsAlert.objects.filter(alert_type="PERFORMANCE")
        print(f"DEBUG: Performance alerts count: {performance_alerts.count()}")
        self.assertEqual(
            performance_alerts.count(),
            0,
            "Single failing record should not trigger performance alert",
        )

        # Verify no alerts of any type were created
        print(f"DEBUG: Total alerts count: {AnalyticsAlert.objects.count()}")
        self.assertEqual(
            AnalyticsAlert.objects.count(),
            0,
            "No alerts should be created for single failing record",
        )

        # Debug: Check what the task found for low performance
        print("\nDEBUG: Checking task logic for low performance...")
        low_performers = (
            AcademicRecord.objects.filter(score__lt=40)
            .values("student", "student__school")
            .annotate(
                low_count=Count("id"),
                student_name=Concat(
                    "student__first_name", Value(" "), "student__last_name"
                ),
            )
        )
        print(f"DEBUG: Low performers query count: {low_performers.count()}")
        for performer in low_performers:
            print(
                f"  - Student: {performer['student']}, Count: {performer['low_count']}"
            )

        # Additional debug: Check if any existing alerts might be interfering
        existing_alerts = AnalyticsAlert.objects.filter(
            school_id=self.school.id,
            alert_type="PERFORMANCE",
            related_id=self.student.id,
            resolved_at__isnull=True,
        )
        print(
            f"DEBUG: Existing performance alerts for student: {existing_alerts.count()}"
        )

        # Test 3: Consistent low performance (3 failing records - should trigger alert)
        print("\n--- Test 3: Three failing records ---")
        with transaction.atomic():
            AcademicRecord.objects.all().delete()
            AnalyticsAlert.objects.all().delete()
            print("DEBUG: Cleared all academic records and alerts")

            # Create 3 failing records with different subjects
            subjects = [
                create_test_subject(self.school, name=f"Subject {i}") for i in range(3)
            ]
            for i, subject in enumerate(subjects):
                record = create_test_academic_record(
                    self.student,
                    subject,
                    self.teacher,
                    score=30 + i,  # Scores 30, 31, 32
                    term=f"Term{i+1}",
                    school_year="2023",
                )
                print(
                    f"DEBUG: Created failing record {i+1}: {record.id} with score {record.score}"
                )

        # Debug: Verify records in DB
        records = AcademicRecord.objects.all()
        print(f"DEBUG: Records in DB: {records.count()}")
        for r in records:
            print(
                f"  - ID: {r.id}, Student: {r.student.id}, Subject: {r.subject.id}, Score: {r.score}"
            )

        result = check_and_generate_alerts.delay()
        self.assertTrue(result.successful())

        alerts = AnalyticsAlert.objects.all()
        print(f"DEBUG: Alerts after three failing records: {alerts.count()}")
        for alert in alerts:
            print(
                f"  - Type: {alert.alert_type}, Title: {alert.title}, Related: {alert.related_model}"
            )

        self.assertEqual(
            alerts.count(), 1, "Should create 1 performance alert for 3 failing records"
        )
        self.assertEqual(
            alerts[0].alert_type, "PERFORMANCE", "Alert should be of type PERFORMANCE"
        )

        # Test 4: Teacher absence with no notes (should trigger alert)
        print("\n--- Test 4: Single absence without notes ---")
        with transaction.atomic():
            # Clear ALL related data
            AcademicRecord.objects.all().delete()
            TeacherAttendance.objects.all().delete()
            AnalyticsAlert.objects.all().delete()

            # Create absence with empty notes
            absence = create_test_teacher_attendance(
                self.teacher,
                status="ABSENT",
                notes="",
                date=timezone.now().date(),
            )

        result = check_and_generate_alerts.delay()
        self.assertTrue(result.successful())

        alerts = AnalyticsAlert.objects.all()
        self.assertEqual(
            alerts.count(), 1, "Should create 1 alert for absence with no notes"
        )
        self.assertEqual(alerts[0].alert_type, "ABSENCE_NO_NOTES")

        # Test 5: Frequent absences (3 in last 30 days - should trigger alert)
        with transaction.atomic():
            TeacherAttendance.objects.all().delete()
            AnalyticsAlert.objects.all().delete()

            for i in range(3):  # Create 3 absences
                create_test_teacher_attendance(
                    self.teacher,
                    date=timezone.now().date() - timedelta(days=i),
                    status="ABSENT",
                    notes=f"Notes {i}",  # Add notes to avoid no-notes alert
                )

        result = check_and_generate_alerts.delay()
        self.assertTrue(result.successful())
        alerts = AnalyticsAlert.objects.all()
        self.assertEqual(
            alerts.count(), 1, "Should create 1 alert for frequent absences"
        )
        self.assertEqual(
            alerts[0].alert_type, "ATTENDANCE", "Alert should be of type ATTENDANCE"
        )

        # Test 6: Low class attendance
        print("\n--- Test 6: Low class attendance ---")
        with transaction.atomic():
            # Clear all existing data
            ClassAttendance.objects.all().delete()
            AnalyticsAlert.objects.all().delete()

            # Add a second student to the class
            student2 = create_test_student(
                self.school, teacher=self.teacher, first_name="Student2"
            )
            self.school_class.students.add(student2)

            # Create attendance with only 1 present out of 2 (50%)
            attendance = create_test_class_attendance(
                self.school_class,
                taken_by=self.admin,
                present_students=[self.student],  # Only 1 present
            )

        result = check_and_generate_alerts.delay()
        self.assertTrue(result.successful())

        alerts = AnalyticsAlert.objects.filter(
            alert_type="ATTENDANCE", related_model="schoolclass"
        )
        self.assertEqual(
            alerts.count(), 1, "Should create 1 alert for low class attendance"
        )


# python manage.py test skul_data.tests.analytics_tests.test_analytics_tasks
