# skul_data/schools/management/commands/test_attendance_notifications.py
"""
Management command to test attendance notifications.
Run with: python manage.py test_attendance_notifications
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from skul_data.schools.models.schoolclass import SchoolClass, ClassAttendance
from skul_data.students.models.student import Student
from skul_data.notifications.models.notification import Notification


class Command(BaseCommand):
    help = "Test attendance notification system"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING("\n=== Testing Attendance Notification System ===\n")
        )

        # Get a class with students
        school_class = SchoolClass.objects.filter(students__isnull=False).first()

        if not school_class:
            self.stdout.write(self.style.ERROR("No classes with students found!"))
            return

        self.stdout.write(f"Using class: {school_class.name}")
        self.stdout.write(f"Total students: {school_class.students.count()}")

        # Create test attendance
        attendance = ClassAttendance.objects.create(
            school_class=school_class,
            date=timezone.now().date(),
            taken_by=(
                school_class.class_teacher.user if school_class.class_teacher else None
            ),
            total_students=school_class.students.count(),
        )

        self.stdout.write(f"\nCreated attendance record: {attendance.id}")

        # Mark some students as present
        students = list(school_class.students.all())
        if len(students) >= 2:
            # Mark first student present
            present_student = students[0]
            attendance.present_students.add(present_student)

            # Mark second student absent with reason
            absent_student = students[1]
            attendance.notes = f"{absent_student.full_name}: Medical appointment"
            attendance.save()

            self.stdout.write(f"\nMarked {present_student.full_name} as PRESENT")
            self.stdout.write(f"Marked {absent_student.full_name} as ABSENT")

            # Now trigger notifications manually
            from skul_data.schools.views.schoolclass import ClassAttendanceViewSet

            viewset = ClassAttendanceViewSet()
            viewset._notify_parents_about_attendance(attendance)

            # Check notifications created
            present_notifications = Notification.objects.filter(
                related_model="ClassAttendance",
                related_id=attendance.id,
                title__contains=present_student.full_name,
            )

            absent_notifications = Notification.objects.filter(
                related_model="ClassAttendance",
                related_id=attendance.id,
                title__contains=absent_student.full_name,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Created {present_notifications.count()} notification(s) for present student"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created {absent_notifications.count()} notification(s) for absent student"
                )
            )

            # Show notification details
            self.stdout.write("\n--- Notifications Created ---")
            for notif in present_notifications:
                self.stdout.write(f"\nTo: {notif.user.email}")
                self.stdout.write(f"Title: {notif.title}")
                self.stdout.write(f"Type: {notif.notification_type}")

            for notif in absent_notifications:
                self.stdout.write(f"\nTo: {notif.user.email}")
                self.stdout.write(f"Title: {notif.title}")
                self.stdout.write(f"Type: {notif.notification_type}")

            self.stdout.write(
                self.style.SUCCESS(
                    "\n✓ Test completed! Check your console for email output (if using console backend)"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "\nNote: Emails are currently set to console backend in development."
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "Your developer can configure SMTP for production email sending."
                )
            )

        else:
            self.stdout.write(self.style.ERROR("Not enough students in class to test"))

        # Cleanup test data
        self.stdout.write("\nCleaning up test data...")
        attendance.delete()
        self.stdout.write(self.style.SUCCESS("Done!\n"))
