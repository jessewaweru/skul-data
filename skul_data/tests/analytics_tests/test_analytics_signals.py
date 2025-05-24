from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from skul_data.students.models.student import StudentStatus
from skul_data.users.models.teacher import TeacherAttendance
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.reports.models.report import GeneratedReport, ReportTemplate
from skul_data.schools.models.schoolclass import ClassAttendance
from skul_data.analytics.models.analytics import AnalyticsAlert
from skul_data.tests.analytics_tests.test_helpers import (
    create_test_school,
    create_test_teacher,
    create_test_parent,
    create_test_student,
    create_test_class,
    create_test_document,
    create_test_subject,
    create_test_document_category,
)
from django.core.files.uploadedfile import SimpleUploadedFile
from skul_data.documents.models.document import Document


class AnalyticsSignalsTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(
            self.school, teacher=self.teacher, parent=self.parent
        )
        self.school_class = create_test_class(self.school)

    def test_student_status_alert(self):
        original_status = self.student.status
        self.student.status = StudentStatus.SUSPENDED
        self.student.save()

        # Debug
        print(f"Changed status from {original_status} to {self.student.status}")
        alerts = AnalyticsAlert.objects.filter(alert_type="STUDENT")
        print(f"Status change alerts: {alerts.count()}")

        alert = alerts.first()
        self.assertIsNotNone(alert)

    # def test_low_performance_alert(self):
    #     math_subject = create_test_subject(self.school, name="Math")
    #     record = AcademicRecord.objects.create(
    #         student=self.student,
    #         subject=math_subject,
    #         score=35,  # Below 40 threshold
    #         term="Term 1",
    #         school_year="2023",
    #         teacher=self.teacher,
    #     )

    #     # Debug: Check if signal ran
    #     print(f"Created record with score: {record.score}")
    #     alerts = AnalyticsAlert.objects.all()
    #     print(f"Alerts in DB: {alerts.count()}")

    #     alert = AnalyticsAlert.objects.filter(
    #         alert_type="PERFORMANCE", related_id=record.id
    #     ).first()
    #     self.assertIsNotNone(alert)

    def test_low_performance_alert(self):
        math_subject = create_test_subject(self.school, name="Math")
        record = AcademicRecord.objects.create(
            student=self.student,
            subject=math_subject,
            score=35,  # Below 40 threshold
            term="Term 1",
            school_year="2023",
            teacher=self.teacher,
        )

        # Debug: Check if signal ran
        print(f"Created record with score: {record.score}")
        alerts = AnalyticsAlert.objects.all()
        print(f"Alerts in DB: {alerts.count()}")
        for alert in alerts:
            print(f" - Alert type: {alert.alert_type}, Related: {alert.related_model}")

        # Changed from PERFORMANCE to PERFORMANCE_SINGLE
        alert = AnalyticsAlert.objects.filter(
            alert_type="PERFORMANCE_SINGLE",  # Updated alert type
            related_model="AcademicRecord",  # Now points to record, not student
            related_id=record.id,
        ).first()

        self.assertIsNotNone(alert, "No PERFORMANCE_SINGLE alert was created")
        if alert:
            self.assertEqual(
                alert.title, f"Low Score: {self.student.full_name} in Math"
            )
            self.assertIn(str(record.score), alert.message)

    def test_teacher_absence_alert(self):
        attendance = TeacherAttendance.objects.create(
            teacher=self.teacher,
            date=timezone.now().date(),
            status="ABSENT",
            recorded_by=self.admin,
            notes=None,  # Explicitly set to None
        )

        # Debug
        print(f"Created attendance: {attendance.status}, notes: {attendance.notes}")
        alerts = AnalyticsAlert.objects.filter(alert_type="ATTENDANCE")
        print(f"Attendance alerts: {alerts.count()}")

        alert = alerts.first()
        self.assertIsNotNone(alert)

    def test_consistent_low_performance_alert(self):
        # Create 3 failing records
        for i in range(3):
            subject = create_test_subject(self.school, name=f"Subject {i}")
            AcademicRecord.objects.create(
                student=self.student,
                subject=subject,
                score=30 + i,  # All below 40
                term="Term 1",
                school_year="2023",
                teacher=self.teacher,
            )

        # Debug
        failing_count = AcademicRecord.objects.filter(
            student=self.student, score__lt=40
        ).count()
        print(f"Failing records: {failing_count}")

        alert = AnalyticsAlert.objects.filter(
            alert_type="PERFORMANCE", title__contains="Consistent"
        ).first()
        self.assertIsNotNone(alert)

    def test_frequent_absences_alert(self):
        # Create absences within last 30 days
        for i in range(3):
            TeacherAttendance.objects.create(
                teacher=self.teacher,
                date=timezone.now().date() - timedelta(days=i),
                status="ABSENT",
                recorded_by=self.admin,
            )

        # Debug
        absences = TeacherAttendance.objects.filter(
            teacher=self.teacher,
            status="ABSENT",
            date__gte=timezone.now().date() - timedelta(days=30),
        )
        print(f"Absences in last 30 days: {absences.count()}")

        alert = AnalyticsAlert.objects.filter(
            alert_type="ATTENDANCE", title__contains="Frequent"
        ).first()
        self.assertIsNotNone(alert)

    def test_large_document_alert(self):
        # Create 6MB file content
        large_content = b"0" * 6 * 1024 * 1024
        doc = Document.objects.create(
            title="Large Document",
            school=self.school,
            uploaded_by=self.admin,
            file=SimpleUploadedFile("large.pdf", large_content),
            file_size=6 * 1024 * 1024,  # Explicitly set size
            category=create_test_document_category(self.school),
        )

        # Debug
        print(f"Document size: {doc.file_size} bytes")
        alerts = AnalyticsAlert.objects.filter(alert_type="DOCUMENT")
        print(f"Document alerts: {alerts.count()}")

        alert = alerts.first()
        self.assertIsNotNone(alert)

    def test_late_report_alert(self):
        # Create a report template first
        template = ReportTemplate.objects.create(
            name="Test Template",
            template_type="ACADEMIC",
            content={},
            created_by=self.admin,
        )

        GeneratedReport.objects.create(
            title="Late Report",
            report_type=template,  # Add this
            school=self.school,
            generated_by=self.admin,
            valid_until=timezone.now() - timedelta(days=1),
            generated_at=timezone.now(),
            data={},
            parameters={},
        )

    def test_low_class_attendance_alert(self):
        # Add students to the class
        students = [create_test_student(self.school) for _ in range(10)]
        self.school_class.students.add(*students)

        # Create attendance with 3 present students
        attendance = ClassAttendance.objects.create(
            school_class=self.school_class,
            date=timezone.now().date(),
            taken_by=self.admin,
        )
        attendance.present_students.set(students[:3])
        attendance.save()

        alert = AnalyticsAlert.objects.filter(alert_type="ATTENDANCE").first()
        self.assertIsNotNone(alert)
        self.assertIn("Low Class Attendance", alert.title)


# python manage.py test skul_data.tests.analytics_tests.test_analytics_signals
