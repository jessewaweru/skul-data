# skul_data/schools/management/commands/debug_attendance_notifications.py
"""
Debug command to check why notifications aren't being created.
Run with: python manage.py debug_attendance_notifications
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from skul_data.schools.models.schoolclass import SchoolClass, ClassAttendance
from skul_data.students.models.student import Student
from skul_data.notifications.models.notification import Notification


class Command(BaseCommand):
    help = "Debug attendance notification system"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING("\n=== Debugging Attendance Notification System ===\n")
        )

        # Get a class with students
        school_class = SchoolClass.objects.filter(students__isnull=False).first()

        if not school_class:
            self.stdout.write(self.style.ERROR("No classes with students found!"))
            return

        self.stdout.write(f"Class: {school_class.name}")
        self.stdout.write(f"Total students in class: {school_class.students.count()}\n")

        # Check students and their parents
        students = school_class.students.all()[:3]  # Check first 3 students

        for i, student in enumerate(students, 1):
            self.stdout.write(f"\n--- Student {i} ---")
            self.stdout.write(f"Name: {student.full_name}")
            self.stdout.write(f"ID: {student.id}")

            # Check parent
            if student.parent:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Has parent: {student.parent.user.email}")
                )
            else:
                self.stdout.write(self.style.ERROR("✗ No parent assigned"))

            # Check guardians
            guardians = student.guardians.all()
            if guardians.exists():
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Has {guardians.count()} guardian(s)")
                )
                for guardian in guardians:
                    self.stdout.write(f"  - {guardian.user.email}")
            else:
                self.stdout.write(self.style.ERROR("✗ No guardians assigned"))

        # Find a student WITH a parent
        student_with_parent = Student.objects.filter(
            student_class=school_class, parent__isnull=False
        ).first()

        if not student_with_parent:
            self.stdout.write(
                self.style.ERROR(
                    "\n\n❌ PROBLEM FOUND: No students in this class have parents assigned!"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "\nTo fix: Assign parents to students in the admin panel or through the API."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"\n\n✓ Found student with parent: {student_with_parent.full_name}"
            )
        )

        # Create test attendance with this student
        self.stdout.write("\n--- Creating Test Attendance ---")
        attendance = ClassAttendance.objects.create(
            school_class=school_class,
            date=timezone.now().date(),
            taken_by=(
                school_class.class_teacher.user if school_class.class_teacher else None
            ),
            total_students=school_class.students.count(),
        )

        # Mark the student as present
        attendance.present_students.add(student_with_parent)

        self.stdout.write(f"Created attendance ID: {attendance.id}")
        self.stdout.write(f"Marked {student_with_parent.full_name} as PRESENT")

        # Manually trigger notification
        self.stdout.write("\n--- Triggering Notification ---")

        try:
            from skul_data.schools.views.schoolclass import ClassAttendanceViewSet

            viewset = ClassAttendanceViewSet()

            # Call the method
            viewset._notify_parents_about_attendance(attendance)

            self.stdout.write(self.style.SUCCESS("✓ Notification method executed"))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error calling notification method: {str(e)}")
            )
            import traceback

            self.stdout.write(traceback.format_exc())

        # Check if notifications were created
        notifications = Notification.objects.filter(
            related_model="ClassAttendance", related_id=attendance.id
        )

        self.stdout.write(f"\n--- Results ---")
        self.stdout.write(f"Notifications created: {notifications.count()}")

        if notifications.exists():
            self.stdout.write(
                self.style.SUCCESS("\n✓ SUCCESS! Notifications were created:")
            )
            for notif in notifications:
                self.stdout.write(f"\n  To: {notif.user.email}")
                self.stdout.write(f"  Title: {notif.title}")
                self.stdout.write(f"  Type: {notif.notification_type}")
                self.stdout.write(f"  Message preview: {notif.message[:100]}...")
        else:
            self.stdout.write(
                self.style.ERROR("\n✗ FAILED: No notifications were created")
            )

            # Additional debugging
            self.stdout.write("\n--- Additional Debug Info ---")
            self.stdout.write(f"Student parent: {student_with_parent.parent}")
            self.stdout.write(
                f'Student parent user: {student_with_parent.parent.user if student_with_parent.parent else "None"}'
            )
            self.stdout.write(
                f"Student guardians count: {student_with_parent.guardians.count()}"
            )

        # Check console for email output
        self.stdout.write("\n--- Email Output ---")
        self.stdout.write(
            "Check above this line for email content (should appear if EMAIL_BACKEND is console)"
        )

        # Cleanup
        self.stdout.write("\n--- Cleanup ---")
        attendance.delete()
        self.stdout.write(self.style.SUCCESS("Test data deleted\n"))
